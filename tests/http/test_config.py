from typing import Any

import pytest

from tests.conftest import VALID_ENV, StartServer


def test_no_env_vars_healthcheck_200_webhook_503_one_critical_line(start_server: StartServer) -> None:
    server = start_server(env={**dict.fromkeys(VALID_ENV), 'PATH_PREFIX': '/ai/test'})
    assert server.request('/ai/test/healthcheck').status == 200
    assert server.webhook({'key': 'DO-1'}, secret='x').status == 503
    assert server.output.count('CRITICAL') == 1
    assert 'webhook DISABLED' in server.output


@pytest.mark.parametrize('name', ['WEBHOOK_SECRET', 'AGENT', 'HARNESS'])
def test_missing_required_env_disables_the_webhook(start_server: StartServer, name: str) -> None:
    server = start_server(env={name: None, 'PATH_PREFIX': '/ai/test'})
    assert server.webhook({'key': 'DO-1'}).status == 503
    assert f'missing env vars: {name}' in server.output
    assert server.calls() == []


@pytest.mark.parametrize(
    ('env', 'message'),
    [
        ({'HARNESS': 'cursor'}, 'HARNESS must be one of copilot, claude, gemini, codex, pi'),
        ({'AGENT': 'nope'}, "agent 'nope' not found"),
        ({'AGENT': '../etc'}, "agent '../etc' not found"),
    ],
)
def test_bad_harness_or_agent_disables_the_webhook(start_server: StartServer, env: Any, message: str) -> None:
    server = start_server(env={**env, 'PATH_PREFIX': '/ai/test'})
    assert server.request('/ai/test/healthcheck').status == 200
    assert server.webhook({'key': 'DO-1'}).status == 503
    assert message in server.output


@pytest.mark.parametrize(
    ('agent', 'message'),
    [
        ({'prompt': None}, 'prompt must be a non-empty string'),
        ({'prompt': 'Do {thing}'}, 'prompt uses {thing}, which is not an input field'),
        ({'input': {'key': {}}}, 'input field \'key\' needs a "pattern"'),
        ({'input': {'key': {'pattern': '('}}}, "input field 'key': bad pattern"),
        ({'tools': ['jira(getIssue)']}, '\'jira(getIssue)\' is not an exact "server/tool" entry'),
        ({'tools': ['jira/*']}, "'jira/*' is not an exact"),
        ({'tools': ['other/x']}, 'tools refer to MCP servers missing from mcp.json: other'),
        ({'writeTools': ['other/x']}, 'tools refer to MCP servers missing from mcp.json: other'),
        ({'requiredEnv': ['EXTRA_VAR']}, 'missing env vars: EXTRA_VAR'),
        ({'timeoutSeconds': 0}, 'timeoutSeconds must be > 0'),
        ({'pathPrefix': '/Bad Prefix'}, "invalid pathPrefix '/Bad Prefix'"),
    ],
)
def test_invalid_agent_config_disables_the_webhook(start_server: StartServer, agent: Any, message: str) -> None:
    server = start_server(agent, env={'PATH_PREFIX': '/ai/test'})
    assert server.request('/ai/test/healthcheck').status == 200
    assert server.webhook({'key': 'DO-1'}, prefix='/ai/test').status == 503
    assert message in server.output


@pytest.mark.parametrize(
    ('mcp', 'message'),
    [
        ({'mcpServers': {'jira': {'command': 'x', 'url': 'https://x'}}}, 'needs either "command" or "url"'),
        ({'mcpServers': {'Bad_Name': {'command': 'x'}}}, "mcp server name 'Bad_Name'"),
    ],
)
def test_invalid_mcp_json_disables_the_webhook(start_server: StartServer, mcp: Any, message: str) -> None:
    server = start_server(mcp=mcp)
    assert server.webhook({'key': 'DO-1'}).status == 503
    assert message in server.output


def test_missing_skill_disables_the_webhook(start_server: StartServer) -> None:
    server = start_server(write_skill=False)
    assert server.webhook({'key': 'DO-1'}).status == 503
    assert 'skills/test-skill/SKILL.md missing' in server.output


def test_fully_configured_server_logs_no_critical_line(start_server: StartServer) -> None:
    server = start_server()
    assert 'CRITICAL' not in server.output
    assert 'agent test-agent, harness copilot, dry run false' in server.output
