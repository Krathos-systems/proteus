"""Translates the neutral agent definition into each harness's CLI flags and config files.

Every harness gets the same guarantees for an unattended run: only the agent's MCP servers are
loaded, only the listed MCP tools are allowed, nothing prompts for approval, and built-in tools
that change files or run commands are not granted.
"""

import json
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from runner.config import AGENTS_DIR, HARNESS, Agent

type Command = Callable[[str], list[str]]

# Read-only built-ins for pi; every other harness keeps its own read-only defaults.
PI_READ_ONLY_TOOLS = ['read', 'grep', 'find', 'ls']


def _write_private(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600)
    path.write_text(text)
    return str(path)


def _stdio_or_http(server: dict[str, Any], *, url_key: str = 'url', **http_extra: Any) -> dict[str, Any]:
    if 'url' in server:
        return {url_key: server['url'], 'headers': server.get('headers', {}), **http_extra}
    return {'command': server['command'], 'args': server.get('args', []), 'env': server.get('env', {})}


def _toml(value: Any) -> str:
    # Enough TOML for strings, lists and string tables; JSON string escapes are valid TOML.
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, list):
        return '[' + ', '.join(_toml(item) for item in value) + ']'
    if isinstance(value, dict):
        return '{ ' + ', '.join(f'{_toml(str(k))} = {_toml(v)}' for k, v in value.items()) + ' }'
    raise TypeError(f'cannot write {type(value).__name__} as TOML')


def _pi_name(name: str) -> str:
    return re.sub(r'\W', '_', name)


def _copilot(agent: Agent, state: Path, workspace: Path, servers: dict[str, Any]) -> tuple[Command, dict[str, str]]:
    args = ['--silent', '--no-ask-user', '--disable-builtin-mcps']
    if servers:
        config = {
            name: {'type': 'http' if 'url' in s else 'local', **_stdio_or_http(s), 'tools': agent.tools[name]}
            for name, s in servers.items()
        }
        path = _write_private(state / 'copilot-mcp.json', json.dumps({'mcpServers': config}))
        args += ['--additional-mcp-config', f'@{path}']
    for server, names in agent.tools.items():
        args += [arg for name in names for arg in ('--allow-tool', f'{server}({name})')]
    if agent.model:
        args += ['--model', agent.model]
    return lambda prompt: ['copilot', '-p', prompt, *args], {}


def _claude(agent: Agent, state: Path, workspace: Path, servers: dict[str, Any]) -> tuple[Command, dict[str, str]]:
    args = ['-p', '--output-format', 'text', '--no-session-persistence', '--permission-mode', 'dontAsk']
    args += ['--strict-mcp-config']
    if servers:
        config = {name: _stdio_or_http(s, type='http') for name, s in servers.items()}
        args += ['--mcp-config', _write_private(state / 'claude-mcp.json', json.dumps({'mcpServers': config}))]
    allowed = [f'mcp__{server}__{name}' for server, names in agent.tools.items() for name in names]
    if allowed:
        args += ['--allowedTools', ','.join(allowed)]
    if agent.model:
        args += ['--model', agent.model]
    return lambda prompt: ['claude', *args, '--', prompt], {}


def _gemini(agent: Agent, state: Path, workspace: Path, servers: dict[str, Any]) -> tuple[Command, dict[str, str]]:
    # trust skips confirmation, but only for the tools includeTools exposes. In headless mode every
    # other tool that needs approval (shell, file writes) is denied.
    config = {
        name: {**_stdio_or_http(s, url_key='httpUrl'), 'includeTools': agent.tools[name], 'trust': True}
        for name, s in servers.items()
    }
    _write_private(workspace / '.gemini' / 'settings.json', json.dumps({'mcpServers': config}))
    args = ['--skip-trust', '--output-format', 'text']
    if agent.model:
        args += ['--model', agent.model]
    return lambda prompt: ['gemini', *args, '-p', prompt], {}


def _codex(agent: Agent, state: Path, workspace: Path, servers: dict[str, Any]) -> tuple[Command, dict[str, str]]:
    lines = ['approval_policy = "never"', 'sandbox_mode = "read-only"']
    for name, server in servers.items():
        lines.append(f'\n[mcp_servers.{name}]')
        if 'url' in server:
            lines += [f'url = {_toml(server["url"])}', f'http_headers = {_toml(server.get("headers", {}))}']
        else:
            lines += [
                f'command = {_toml(server["command"])}',
                f'args = {_toml(server.get("args", []))}',
                f'env = {_toml(server.get("env", {}))}',
            ]
        lines += [f'enabled_tools = {_toml(agent.tools[name])}', 'default_tools_approval_mode = "approve"']
    codex_home = state / 'codex'
    _write_private(codex_home / 'config.toml', '\n'.join(lines) + '\n')
    args = ['exec', '--skip-git-repo-check', '--ephemeral', '--color', 'never', '--sandbox', 'read-only']
    args += ['-C', str(workspace)]
    if agent.model:
        args += ['--model', agent.model]
    return lambda prompt: ['codex', *args, '--', prompt], {'CODEX_HOME': str(codex_home)}


def _pi(agent: Agent, state: Path, workspace: Path, servers: dict[str, Any]) -> tuple[Command, dict[str, str]]:
    config = {name: {**_stdio_or_http(s), 'exposure': 'direct'} for name, s in servers.items()}
    pi_dir = state / 'pi'
    _write_private(pi_dir / 'mcp.json', json.dumps({'mcpServers': config}))
    tools = PI_READ_ONLY_TOOLS + [
        f'mcp__{_pi_name(server)}__{_pi_name(name)}' for server, names in agent.tools.items() for name in names
    ]
    args = ['-p', '--no-session', '--no-approve', '--no-context-files', '--no-skills', '--tools', ','.join(tools)]
    if agent.skill:
        args += ['--skill', str(workspace / '.agents' / 'skills' / agent.skill)]
    if not servers:
        args += ['--no-mcp']
    if agent.model:
        args += ['--model', agent.model]
    return lambda prompt: ['pi', *args, '--', prompt], {'PI_CODING_AGENT_DIR': str(pi_dir)}


ADAPTERS = {'copilot': _copilot, 'claude': _claude, 'gemini': _gemini, 'codex': _codex, 'pi': _pi}
SKILLS_DIR = {'copilot': '.github/skills', 'claude': '.claude/skills'}  # the rest read .agents/skills


def prepare(agent: Agent) -> tuple[Command, dict[str, str], Path]:
    """Writes the harness config into a private state dir; returns (command builder, extra env, cwd)."""
    # mkdtemp is 0700, so the configs with expanded secrets stay private to this user.
    state = Path(tempfile.mkdtemp(prefix='proteus-'))
    workspace = state / 'workspace'
    workspace.mkdir()
    if agent.skill:
        shutil.copytree(AGENTS_DIR / agent.name / 'skills', workspace / SKILLS_DIR.get(HARNESS, '.agents/skills'))
    # Only servers with at least one allowed tool are started.
    servers = {name: server for name, server in agent.mcp_servers.items() if agent.tools.get(name)}
    command, env = ADAPTERS[HARNESS](agent, state, workspace, servers)
    return command, env, workspace
