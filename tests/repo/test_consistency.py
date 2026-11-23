import re
import tomllib

from tests.conftest import HARNESSES, ROOT

COMPOSE = (ROOT / 'docker-compose.yml').read_text()
DOCKERFILE = (ROOT / 'Dockerfile').read_text()
WORKFLOW = (ROOT / '.github' / 'workflows' / 'ci.yml').read_text()
PYPROJECT = tomllib.loads((ROOT / 'pyproject.toml').read_text())


def test_image_installs_and_pins_every_harness_cli() -> None:
    packages = {
        'copilot': '@github/copilot',
        'claude': '@anthropic-ai/claude-code',
        'gemini': '@google/gemini-cli',
        'codex': '@openai/codex',
        'pi': '@earendil-works/pi-coding-agent',
    }
    assert set(packages) == set(HARNESSES)
    for harness, package in packages.items():
        assert re.search(rf'"{re.escape(package)}@\$\{{{harness.upper()}_VERSION\}}"', DOCKERFILE), harness
        assert re.search(rf'ARG {harness.upper()}_VERSION=\d+\.\d+\.\d+', DOCKERFILE), harness


def test_smoke_test_checks_every_harness_cli() -> None:
    for harness in HARNESSES:
        assert f'{harness} --version' in COMPOSE, harness


def test_dockerfile_runs_the_runner_from_mounted_agents() -> None:
    assert re.search(r'COPY runner/ \./runner/', DOCKERFILE)
    assert 'AGENTS_DIR=/agents' in DOCKERFILE
    assert '"python", "-m", "runner"' in DOCKERFILE


def test_compose_mounts_agents_read_only_and_host_ports_are_unique() -> None:
    assert './agents:/agents:ro' in COMPOSE
    ports = re.findall(r'"127\.0\.0\.1:(\d+):3000"', COMPOSE)
    assert ports
    assert len(set(ports)) == len(ports)


def test_no_real_secrets_in_compose_files() -> None:
    for file in ['docker-compose.yml', 'docker-compose.development.yml', 'docker-compose.override.EXAMPLE.yml']:
        text = (ROOT / file).read_text()
        assert not re.search(r'ghp_[A-Z0-9]{20,}|github_pat_|sk-[A-Za-z0-9-]{20,}|AIza[0-9A-Za-z_-]{30,}', text), file


def test_override_file_stays_gitignored() -> None:
    assert 'docker-compose.override.yml' in (ROOT / '.gitignore').read_text()
    assert (ROOT / 'docker-compose.override.EXAMPLE.yml').exists()


def test_ci_lints_typechecks_tests_and_smoke_tests_the_image() -> None:
    for command in ['uv run ruff check', 'uv run ruff format --check', 'uv run mypy', 'uv run pytest']:
        assert command in WORKFLOW
    assert 'docker compose --profile bvt run --rm bvt' in WORKFLOW


def test_python_version_matches_and_runtime_has_no_dependencies() -> None:
    project = PYPROJECT['project']
    version = (ROOT / '.python-version').read_text().strip()
    assert project['requires-python'] == f'>={version}'
    assert project['dependencies'] == []
    assert f'FROM python:{version}-slim' in DOCKERFILE
