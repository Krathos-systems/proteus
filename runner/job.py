import itertools
import json
from dataclasses import dataclass

from runner.config import DRY_RUN, PROMPT_FIELD_RE, agent

DRY_RUN_NOTE = (
    ' This is a dry run: do not create, change or post anything.'
    ' Reply with only the result you would have produced or posted.'
)
_ids = itertools.count(1)


@dataclass(frozen=True)
class Job:
    id: int
    prompt: str

    @property
    def label(self) -> str:
        return f'job {self.id}'


class BadRequestError(Exception):
    pass


# Validates the payload against the agent's input fields; raises BadRequestError when it is not acceptable.
def parse_job(raw: bytes) -> Job:
    try:
        payload = json.loads(raw)
    except ValueError:
        raise BadRequestError('bad json') from None
    if not isinstance(payload, dict):
        raise BadRequestError('body must be a JSON object')

    values = {'skill': agent.skill}
    for name, spec in agent.inputs.items():
        value = payload.get(name)
        if value is None:
            if spec.required:
                raise BadRequestError(f'{name} required')
            value = ''
        elif not isinstance(value, str) or not spec.pattern.fullmatch(value):
            raise BadRequestError(f'invalid {name}')
        values[name] = value

    prompt = PROMPT_FIELD_RE.sub(lambda match: values[match[1]], agent.prompt)
    return Job(id=next(_ids), prompt=prompt + (DRY_RUN_NOTE if DRY_RUN else ''))
