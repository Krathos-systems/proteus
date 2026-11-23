"""`python -m runner new NAME`: copies the example agent into agents/NAME and renames it."""

import argparse
import json
import re
import shutil
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / 'examples' / 'hello-agent'
TEMPLATE_SKILL = 'hello-skill'
NAME_RE = re.compile(r'[a-z0-9][a-z0-9-]*')


def create_agent(name: str, agents_dir: Path) -> Path:
    if not NAME_RE.fullmatch(name):
        raise ValueError(f'{name!r} is not a valid agent name (lowercase letters, digits and -)')
    target = agents_dir / name
    if target.exists():
        raise FileExistsError(f'{target} already exists')
    shutil.copytree(TEMPLATE, target)

    skill = f'{name}-skill'
    (target / 'skills' / TEMPLATE_SKILL).rename(target / 'skills' / skill)
    skill_file = target / 'skills' / skill / 'SKILL.md'
    skill_file.write_text(skill_file.read_text().replace(f'name: {TEMPLATE_SKILL}', f'name: {skill}', 1))

    config = json.loads((target / 'agent.json').read_text())
    config.update(pathPrefix=f'/{name}', skill=skill)
    (target / 'agent.json').write_text(json.dumps(config, indent=2) + '\n')
    return target


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog='python -m runner new', description=__doc__)
    parser.add_argument('name', help='agent name, e.g. issue-triage')
    parser.add_argument('--dir', type=Path, default=Path('agents'), help='agents directory (default: ./agents)')
    args = parser.parse_args(argv)
    try:
        target = create_agent(args.name, args.dir)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f'Created {target}. Edit agent.json, the skill in skills/ and (optionally) mcp.json.')
    print(f'Run it: AGENT={args.name} AGENTS_DIR={args.dir} HARNESS=claude WEBHOOK_SECRET=... python -m runner')
    return 0
