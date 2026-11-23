import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
HARNESSES = ['copilot', 'claude', 'gemini', 'codex', 'pi']

VALID_ENV = {
    'AGENT': 'test-agent',
    'HARNESS': 'copilot',
    'JIRA_AUTH': 'dGVzdA==',
    'WEBHOOK_SECRET': 's3cret',
}
DEFAULT_AGENT: dict[str, Any] = {
    'pathPrefix': '/ai/test',
    'skill': 'test-skill',
    'prompt': 'Use the {skill} skill for issue {key} ({summary}).',
    'input': {
        'key': {'pattern': r'[A-Z][A-Z0-9]+-\d+'},
        'summary': {'pattern': '[^"\\n\\r]{0,200}', 'required': False},
    },
    'tools': ['jira/getIssue'],
    'writeTools': ['jira/addComment'],
    'models': {'copilot': 'test-model'},
    'timeoutSeconds': 5,
}
DEFAULT_MCP: dict[str, Any] = {
    'mcpServers': {
        'jira': {'url': 'https://mcp.example.com/mcp', 'headers': {'Authorization': 'Basic ${JIRA_AUTH}'}},
        'unused': {'command': 'unused-server', 'args': ['--x']},
    }
}
SERVER_START_TIMEOUT = 10.0
UNSET = object()  # webhook(secret=UNSET) sends the server's own secret

# Records each call as one JSON line: harness, args, cwd, relevant env, the config files it was given and skills.
RECORDER = """
import json, os, sys, time
calls_file, harness, args = sys.argv[1], os.path.basename(sys.argv[2]), sys.argv[3:]
files, modes = {}, {}
def grab(key, path):
    try:
        files[key] = open(path).read()
        modes[key] = oct(os.stat(path).st_mode & 0o777)
    except OSError:
        pass
for flag in ('--additional-mcp-config', '--mcp-config'):
    if flag in args:
        grab('mcp', args[args.index(flag) + 1].lstrip('@'))
if os.environ.get('CODEX_HOME'):
    grab('mcp', os.path.join(os.environ['CODEX_HOME'], 'config.toml'))
if os.environ.get('PI_CODING_AGENT_DIR'):
    grab('mcp', os.path.join(os.environ['PI_CODING_AGENT_DIR'], 'mcp.json'))
grab('mcp', os.path.join(os.getcwd(), '.gemini', 'settings.json'))
skills = sorted(
    os.path.relpath(os.path.join(d, f), os.getcwd())
    for d, _, fs in os.walk(os.getcwd()) for f in fs if f == 'SKILL.md'
)
keep = ('CODEX_HOME', 'PI_CODING_AGENT_DIR', 'WEBHOOK_SECRET', 'JIRA_AUTH')
env = {k: os.environ[k] for k in keep if k in os.environ}
with open(calls_file, 'a') as f:
    f.write(json.dumps({'harness': harness, 'args': args, 'cwd': os.getcwd(), 'env': env,
                        'mcp': files.get('mcp'), 'mcp_mode': modes.get('mcp'), 'skills': skills,
                        'at': time.time()}) + '\\n')
"""


def wait_for[T](check: Callable[[], T], timeout: float = 5.0, interval: float = 0.025) -> T:
    end = time.monotonic() + timeout
    while True:
        value = check()
        if value:
            return value
        if time.monotonic() > end:
            raise TimeoutError('wait_for timed out')
        time.sleep(interval)


@dataclass
class Response:
    status: int
    text: str


@dataclass
class TestServer:
    __test__ = False  # not a pytest test class

    agents_dir: Path
    bin_dir: Path
    port: int
    env: dict[str, str]
    calls_file: Path
    process: subprocess.Popen[bytes]
    _output: list[str] = field(default_factory=list)

    @property
    def output(self) -> str:
        return ''.join(self._output)

    def calls(self) -> list[dict[str, Any]]:
        if not self.calls_file.exists():
            return []
        return [json.loads(line) for line in self.calls_file.read_text().splitlines() if line]

    def request(
        self, path: str, method: str = 'GET', body: bytes | None = None, headers: dict[str, str] | None = None
    ) -> Response:
        req = urllib.request.Request(
            f'http://127.0.0.1:{self.port}{path}', data=body, method=method, headers=headers or {}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                return Response(res.status, res.read().decode())
        except urllib.error.HTTPError as error:
            return Response(error.code, error.read().decode())

    def webhook(self, body: Any, *, prefix: str = '/ai/test', raw: bool = False, secret: Any = UNSET) -> Response:
        if secret is UNSET:
            secret = self.env.get('WEBHOOK_SECRET')
        headers = {'Content-Type': 'application/json'}
        if secret is not None:
            headers['X-Webhook-Secret'] = secret
        data = (str(body) if raw else json.dumps(body)).encode()
        return self.request(f'{prefix}/webhook', method='POST', body=data, headers=headers)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port: int = probe.getsockname()[1]
        return port


def write_agent(
    agents_dir: Path, name: str, agent: dict[str, Any], mcp: dict[str, Any] | None, skill: str | None
) -> None:
    agent_dir = agents_dir / name
    agent_dir.mkdir(parents=True)
    (agent_dir / 'agent.json').write_text(json.dumps(agent))
    if mcp is not None:
        (agent_dir / 'mcp.json').write_text(json.dumps(mcp))
    if skill:
        (agent_dir / 'skills' / skill).mkdir(parents=True)
        (agent_dir / 'skills' / skill / 'SKILL.md').write_text(f'---\nname: {skill}\ndescription: test\n---\n')


StartServer = Callable[..., TestServer]


@pytest.fixture
def start_server() -> Iterator[StartServer]:
    """Starts `python -m runner` against a throw-away agents dir with fake harness CLIs on PATH.

    agent: overrides merged into DEFAULT_AGENT (a None value removes the key).
    agent_dir: copy this directory as the agent instead (e.g. examples/hello-agent).
    copilot: shell run by every fake harness after recording the call ("$2" is copilot's prompt).
    Every instance has its own temp dir and port, so tests can run in parallel.
    """
    started: list[tuple[TestServer, Path]] = []

    def start(
        agent: dict[str, Any] | None = None,
        *,
        agent_dir: Path | None = None,
        mcp: dict[str, Any] | None = DEFAULT_MCP,
        copilot: str = 'echo "fake result"',
        env: dict[str, str | None] | None = None,
        write_skill: bool = True,
    ) -> TestServer:
        tmp = Path(tempfile.mkdtemp(prefix='runner-test-'))
        agents_dir, bin_dir, home = tmp / 'agents', tmp / 'bin', tmp / 'home'
        for directory in (agents_dir, bin_dir, home):
            directory.mkdir()
        if agent_dir:
            shutil.copytree(agent_dir, agents_dir / 'test-agent')
        else:
            merged = {k: v for k, v in {**DEFAULT_AGENT, **(agent or {})}.items() if v is not None}
            write_agent(agents_dir, 'test-agent', merged, mcp, merged.get('skill') if write_skill else None)

        calls_file = tmp / 'calls.jsonl'
        (tmp / 'recorder.py').write_text(RECORDER)
        for harness in HARNESSES:
            fake = bin_dir / harness
            fake.write_text(
                f'#!/bin/sh\n"{sys.executable}" "{tmp / "recorder.py"}" "{calls_file}" "$0" "$@"\n{copilot}\n'
            )
            fake.chmod(0o755)

        port = _free_port()
        merged_env: dict[str, str | None] = {
            'AGENTS_DIR': str(agents_dir),
            'HOME': str(home),
            'PATH': f'{bin_dir}:{os.environ["PATH"]}',
            'PORT': str(port),
            **VALID_ENV,
            **(env or {}),
        }
        child_env = {k: v for k, v in merged_env.items() if v is not None}
        process = subprocess.Popen(
            [sys.executable, '-m', 'runner'],
            cwd=ROOT,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        server = TestServer(agents_dir, bin_dir, port, child_env, calls_file, process)

        def collect() -> None:
            assert process.stdout
            for line in iter(process.stdout.readline, b''):
                server._output.append(line.decode())

        threading.Thread(target=collect, daemon=True).start()
        started.append((server, tmp))
        wait_for(lambda: 'started on port' in server.output, timeout=SERVER_START_TIMEOUT)
        return server

    yield start
    for server, tmp in started:
        server.process.kill()
        server.process.wait()
        shutil.rmtree(tmp, ignore_errors=True)
