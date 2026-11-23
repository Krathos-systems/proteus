import json
import tomllib
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import HARNESSES, StartServer, TestServer, wait_for

PROMPT = 'Use the test-skill skill for issue DO-1 (hi).'


def first_call(server: TestServer, body: Any = None) -> dict[str, Any]:
    assert server.webhook(body or {'key': 'DO-1', 'summary': 'hi'}).status == 202
    call: dict[str, Any] = wait_for(server.calls)[0]
    return call


def values(args: list[str], flag: str) -> list[str]:
    return [args[i + 1] for i, arg in enumerate(args) if arg == flag]


def allowed_tools(call: dict[str, Any]) -> list[str]:
    """The tool allowlist each harness actually received, in its own naming."""
    args, harness = call['args'], call['harness']
    if harness == 'copilot':
        return values(args, '--allow-tool')
    if harness == 'claude':
        return ','.join(values(args, '--allowedTools')).split(',') if '--allowedTools' in args else []
    if harness == 'gemini':
        return [t for s in json.loads(call['mcp'])['mcpServers'].values() for t in s['includeTools']]
    if harness == 'codex':
        return [t for s in tomllib.loads(call['mcp']).get('mcp_servers', {}).values() for t in s['enabled_tools']]
    return [t for t in values(args, '--tools')[0].split(',') if t.startswith('mcp__')]


EXPECTED_TOOLS = {
    'copilot': (['jira(getIssue)'], ['jira(addComment)']),
    'claude': (['mcp__jira__getIssue'], ['mcp__jira__addComment']),
    'gemini': (['getIssue'], ['addComment']),
    'codex': (['getIssue'], ['addComment']),
    'pi': (['mcp__jira__getIssue'], ['mcp__jira__addComment']),
}
SKILL_DIRS = {'copilot': '.github/skills', 'claude': '.claude/skills'}


def mcp_servers(call: dict[str, Any]) -> dict[str, Any]:
    if call['harness'] == 'codex':
        servers: dict[str, Any] = tomllib.loads(call['mcp']).get('mcp_servers', {})
        return servers
    servers = json.loads(call['mcp'])['mcpServers']
    return servers


@pytest.mark.parametrize('harness', HARNESSES)
def test_live_run_gets_the_prompt_read_and_write_tools_and_only_used_servers(
    start_server: StartServer, harness: str
) -> None:
    call = first_call(start_server(env={'HARNESS': harness}))
    assert call['harness'] == harness
    assert PROMPT in call['args']
    read, write = EXPECTED_TOOLS[harness]
    assert allowed_tools(call) == read + write
    # Only servers with an allowed tool are configured, with ${VAR} expanded, in a private file.
    servers = mcp_servers(call)
    assert list(servers) == ['jira']
    assert 'Basic dGVzdA==' in call['mcp']
    assert '${' not in call['mcp']
    assert call['mcp_mode'] == '0o600'
    # The skill is where the harness discovers it, and the webhook secret never reaches the agent.
    assert call['skills'] == [f'{SKILL_DIRS.get(harness, ".agents/skills")}/test-skill/SKILL.md']
    assert 'WEBHOOK_SECRET' not in call['env']
    assert call['env']['JIRA_AUTH'] == 'dGVzdA=='


@pytest.mark.parametrize('harness', HARNESSES)
def test_dry_run_withholds_write_tools_and_says_so(start_server: StartServer, harness: str) -> None:
    call = first_call(start_server(env={'HARNESS': harness, 'DRY_RUN': 'true'}))
    assert allowed_tools(call) == EXPECTED_TOOLS[harness][0]
    prompt = next(arg for arg in call['args'] if arg.startswith(PROMPT))
    assert 'This is a dry run' in prompt


@pytest.mark.parametrize('harness', HARNESSES)
def test_agent_without_tools_starts_no_mcp_server(start_server: StartServer, harness: str) -> None:
    call = first_call(start_server({'tools': [], 'writeTools': []}, env={'HARNESS': harness}))
    assert allowed_tools(call) == []
    assert call['mcp'] is None or mcp_servers(call) == {}


def test_harness_specific_unattended_flags(start_server: StartServer) -> None:
    calls = {h: first_call(start_server(env={'HARNESS': h})) for h in HARNESSES}
    copilot, claude, gemini, codex, pi = (calls[h]['args'] for h in HARNESSES)
    assert copilot[:2] == ['-p', PROMPT]
    assert {'--silent', '--no-ask-user', '--disable-builtin-mcps'} <= set(copilot)
    assert values(claude, '--permission-mode') == ['dontAsk']
    assert {'-p', '--strict-mcp-config', '--no-session-persistence'} <= set(claude)
    assert claude[-2:] == ['--', PROMPT]
    assert values(gemini, '-p') == [PROMPT]
    assert '--skip-trust' in gemini
    assert codex[0] == 'exec'
    assert values(codex, '--sandbox') == ['read-only']
    assert values(codex, '-C') == [calls['codex']['cwd']]
    config = tomllib.loads(calls['codex']['mcp'])
    assert config['approval_policy'] == 'never'
    assert config['mcp_servers']['jira']['default_tools_approval_mode'] == 'approve'
    assert Path(calls['codex']['env']['CODEX_HOME'], 'config.toml').parent.name == 'codex'
    assert values(pi, '--tools')[0].split(',')[:4] == ['read', 'grep', 'find', 'ls']
    assert {'-p', '--no-session', '--no-approve', '--no-skills'} <= set(pi)
    assert values(pi, '--skill')[0].endswith('.agents/skills/test-skill')
    assert json.loads(calls['pi']['mcp'])['mcpServers']['jira']['exposure'] == 'direct'


def test_stdio_and_http_servers_are_translated(start_server: StartServer) -> None:
    mcp = {
        'mcpServers': {
            'local-db': {'command': 'db-mcp', 'args': ['--ro'], 'env': {'TOKEN': '${JIRA_AUTH}'}},
            'jira': {'url': 'https://mcp.example.com/mcp'},
        }
    }
    agent = {'tools': ['local-db/query', 'jira/getIssue'], 'writeTools': []}
    for harness in HARNESSES:
        servers = mcp_servers(first_call(start_server(agent, mcp=mcp, env={'HARNESS': harness})))
        assert servers['local-db']['command'] == 'db-mcp', harness
        assert servers['local-db']['args'] == ['--ro'], harness
        assert servers['local-db']['env'] == {'TOKEN': 'dGVzdA=='}, harness
        url_key = 'httpUrl' if harness == 'gemini' else 'url'
        assert servers['jira'][url_key] == 'https://mcp.example.com/mcp', harness


def test_pi_tool_names_are_sanitised(start_server: StartServer) -> None:
    mcp = {'mcpServers': {'my-db': {'command': 'x'}}}
    call = first_call(start_server({'tools': ['my-db/run.query'], 'writeTools': []}, mcp=mcp, env={'HARNESS': 'pi'}))
    assert allowed_tools(call) == ['mcp__my_db__run_query']


@pytest.mark.parametrize(
    ('env', 'expected'),
    [({}, ['test-model']), ({'MODEL': 'override'}, ['override']), ({'HARNESS': 'claude'}, [])],
)
def test_model_comes_from_models_map_or_the_model_env(start_server: StartServer, env: Any, expected: Any) -> None:
    assert values(first_call(start_server(env=env))['args'], '--model') == expected
