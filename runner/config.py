import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from runner.logger import register_secrets

# An agent is a directory (agents/<name>/) with agent.json, an optional mcp.json and skills/.
# Secrets come from the environment. Nothing here may raise: the server must always start and
# answer health checks, even when unconfigured.

DEFAULT_PORT = 3000
DEFAULT_TIMEOUT_SECONDS = 600
HARNESSES = ('copilot', 'claude', 'gemini', 'codex', 'pi')
SECRET_NAME_RE = re.compile(r'SECRET|PASSWORD|TOKEN|AUTH|KEY|CREDENTIAL')
PLACEHOLDER_RE = re.compile(r'\$\{(\w+)\}')
PROMPT_FIELD_RE = re.compile(r'\{(\w+)\}')
NAME_RE = re.compile(r'[a-z0-9][a-z0-9-]*')
TOOL_RE = re.compile(r'([A-Za-z0-9_-]+)/([A-Za-z0-9_.-]+)')

# Required (webhook returns 503 without them): these plus the agent's requiredEnv.
REQUIRED_ENV = ['WEBHOOK_SECRET', 'AGENT', 'HARNESS']

PORT = int(os.environ.get('PORT', DEFAULT_PORT))
AGENTS_DIR = Path(os.environ.get('AGENTS_DIR', '/agents'))
AGENT_NAME = os.environ.get('AGENT', '')
HARNESS = os.environ.get('HARNESS', '').lower()
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')
# Write tools are withheld and the agent is told to only report what it would do.
DRY_RUN = os.environ.get('DRY_RUN') == 'true'

config_errors: list[str] = []

# Every env value with a secret-looking name is masked in the logs, whatever logged it.
register_secrets([value for name, value in os.environ.items() if SECRET_NAME_RE.search(name)])


@dataclass(frozen=True)
class InputField:
    pattern: re.Pattern[str]
    required: bool


@dataclass
class Agent:
    name: str = ''
    path_prefix: str = ''
    skill: str = ''
    prompt: str = ''
    inputs: dict[str, InputField] = field(default_factory=dict)
    # Tools as {mcp server: [tool, ...]}; write tools are dropped in dry run.
    tools: dict[str, list[str]] = field(default_factory=dict)
    model: str = ''
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    # mcpServers from mcp.json, with ${VAR} placeholders expanded.
    mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)


class ConfigError(Exception):
    pass


def _check(condition: object, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def _parse_tools(raw: object, label: str, into: dict[str, list[str]]) -> None:
    _check(isinstance(raw, list), f'{label} must be a list of "server/tool" strings')
    assert isinstance(raw, list)
    for entry in raw:
        match = TOOL_RE.fullmatch(entry) if isinstance(entry, str) else None
        _check(match, f'{label}: {entry!r} is not an exact "server/tool" entry')
        assert match
        into.setdefault(match[1], []).append(match[2])


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        return PLACEHOLDER_RE.sub(lambda match: os.environ.get(match[1], ''), value)
    if isinstance(value, list):
        return [_expand(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item) for key, item in value.items()}
    return value


def load_agent(agent_dir: Path, agent: Agent | None = None) -> Agent:
    """Reads and validates agents/<name>/ into agent. Raises ConfigError with a readable message.

    Fields parsed before an error stay set, so an invalid agent still answers on its own prefix.
    """
    agent = agent or Agent(name=agent_dir.name)
    try:
        raw = json.loads((agent_dir / 'agent.json').read_text())
    except (OSError, ValueError) as error:
        raise ConfigError(f'cannot load agent.json: {error}') from None
    _check(isinstance(raw, dict), 'agent.json must be an object')

    agent.path_prefix = str(raw.get('pathPrefix', f'/{agent.name}')).rstrip('/')
    _check(re.fullmatch(r'(/[a-z0-9-]+)+', agent.path_prefix), f'invalid pathPrefix {agent.path_prefix!r}')
    agent.skill = str(raw.get('skill', ''))
    if agent.skill:
        _check((agent_dir / 'skills' / agent.skill / 'SKILL.md').is_file(), f'skills/{agent.skill}/SKILL.md missing')

    agent.prompt = raw.get('prompt', '')
    _check(isinstance(agent.prompt, str) and agent.prompt.strip(), 'prompt must be a non-empty string')

    inputs = raw.get('input', {})
    _check(isinstance(inputs, dict), 'input must be an object of {field: {"pattern": ...}}')
    for name, spec in inputs.items():
        _check(re.fullmatch(r'\w+', name) and isinstance(spec, dict), f'invalid input field {name!r}')
        # Every field needs a pattern: payload values end up in the prompt.
        _check(isinstance(spec.get('pattern'), str), f'input field {name!r} needs a "pattern"')
        try:
            pattern = re.compile(spec['pattern'])
        except re.error as error:
            raise ConfigError(f'input field {name!r}: bad pattern: {error}') from None
        agent.inputs[name] = InputField(pattern, bool(spec.get('required', True)))
    for name in PROMPT_FIELD_RE.findall(agent.prompt):
        _check(name in agent.inputs or name == 'skill', f'prompt uses {{{name}}}, which is not an input field')

    _parse_tools(raw.get('tools', []), 'tools', agent.tools)
    write_tools: dict[str, list[str]] = {}
    _parse_tools(raw.get('writeTools', []), 'writeTools', write_tools)
    for server, names in ({} if DRY_RUN else write_tools).items():
        agent.tools.setdefault(server, []).extend(names)

    models = raw.get('models', {})
    _check(isinstance(models, dict), 'models must be an object of {harness: model}')
    agent.model = os.environ.get('MODEL') or str(models.get(HARNESS, ''))
    agent.timeout_seconds = raw.get('timeoutSeconds', DEFAULT_TIMEOUT_SECONDS)
    _check(isinstance(agent.timeout_seconds, int | float) and agent.timeout_seconds > 0, 'timeoutSeconds must be > 0')

    required = raw.get('requiredEnv', [])
    _check(isinstance(required, list), 'requiredEnv must be a list')
    missing = [name for name in required if not os.environ.get(name)]
    _check(not missing, f'missing env vars: {", ".join(missing)}')

    mcp_file = agent_dir / 'mcp.json'
    if mcp_file.exists():
        try:
            servers = json.loads(mcp_file.read_text()).get('mcpServers', {})
        except (OSError, ValueError, AttributeError) as error:
            raise ConfigError(f'cannot load mcp.json: {error}') from None
        _check(isinstance(servers, dict), 'mcp.json mcpServers must be an object')
        for name, server in servers.items():
            _check(NAME_RE.fullmatch(name), f'mcp server name {name!r} must be lowercase letters, digits and -')
            _check(
                isinstance(server, dict) and ('command' in server) != ('url' in server),
                f'mcp server {name!r} needs either "command" or "url"',
            )
        agent.mcp_servers = _expand(servers)
    unknown = sorted((set(agent.tools) | set(write_tools)) - set(agent.mcp_servers))
    _check(not unknown, f'tools refer to MCP servers missing from mcp.json: {", ".join(unknown)}')
    return agent


def _load() -> Agent:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        config_errors.append(f'missing env vars: {", ".join(missing)}')
    if HARNESS and HARNESS not in HARNESSES:
        config_errors.append(f'HARNESS must be one of {", ".join(HARNESSES)}, not {HARNESS!r}')
    if not AGENT_NAME:
        return Agent()
    if not NAME_RE.fullmatch(AGENT_NAME) or not (AGENTS_DIR / AGENT_NAME).is_dir():
        config_errors.append(f'agent {AGENT_NAME!r} not found in {AGENTS_DIR}')
        return Agent(name=AGENT_NAME)
    agent = Agent(name=AGENT_NAME)
    try:
        load_agent(AGENTS_DIR / AGENT_NAME, agent)
    except ConfigError as error:
        config_errors.append(str(error))
    return agent


agent = _load()
# PATH_PREFIX may override the agent's own pathPrefix.
PREFIX = os.environ.get('PATH_PREFIX', agent.path_prefix).rstrip('/')
