import json
from pathlib import Path

import pytest

from runner.scaffold import create_agent
from tests.conftest import HARNESSES, ROOT, StartServer, wait_for

EXAMPLES = sorted(path for path in (ROOT / 'examples').iterdir() if path.is_dir())


@pytest.mark.parametrize('harness', HARNESSES)
@pytest.mark.parametrize('example', EXAMPLES, ids=lambda path: path.name)
def test_example_agent_boots_and_runs_on_every_harness(start_server: StartServer, example: Path, harness: str) -> None:
    server = start_server(agent_dir=example, env={'HARNESS': harness})
    prefix = json.loads((example / 'agent.json').read_text())['pathPrefix']
    assert 'CRITICAL' not in server.output
    assert server.request(f'{prefix}/healthcheck').status == 200
    assert server.webhook({'name': 'Ada'}, prefix=prefix, secret='bad').status == 401
    assert server.webhook({'name': 'Ada'}, prefix=prefix).status == 202
    call = wait_for(server.calls)[0]
    assert any('greeting for Ada' in arg for arg in call['args'])


def test_scaffold_creates_a_renamed_agent_that_boots(start_server: StartServer, tmp_path: Path) -> None:
    target = create_agent('issue-triage', tmp_path)
    config = json.loads((target / 'agent.json').read_text())
    assert (config['pathPrefix'], config['skill']) == ('/issue-triage', 'issue-triage-skill')
    assert 'name: issue-triage-skill' in (target / 'skills' / 'issue-triage-skill' / 'SKILL.md').read_text()
    server = start_server(agent_dir=target)
    assert 'CRITICAL' not in server.output
    assert server.request('/issue-triage/healthcheck').status == 200


@pytest.mark.parametrize('name', ['Bad', '-x', 'a/b', '../up', ''])
def test_scaffold_rejects_invalid_names(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError, match='not a valid agent name'):
        create_agent(name, tmp_path)


def test_scaffold_never_overwrites(tmp_path: Path) -> None:
    create_agent('mine', tmp_path)
    with pytest.raises(FileExistsError):
        create_agent('mine', tmp_path)
