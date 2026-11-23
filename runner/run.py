import os
import subprocess

from runner.config import HARNESS, agent, config_errors
from runner.harness import Command, prepare
from runner.job import Job
from runner.logger import log

STDERR_TAIL_LENGTH = 500
# The agent never needs the webhook secret.
HIDDEN_ENV = {'WEBHOOK_SECRET'}


class HarnessError(Exception):
    pass


def _prepare() -> tuple[Command | None, dict[str, str], str]:
    if config_errors:
        return None, {}, ''
    try:
        command, extra_env, cwd = prepare(agent)
    except OSError as error:
        config_errors.append(f'cannot prepare the {HARNESS} harness: {error}')
        return None, {}, ''
    env = {name: value for name, value in os.environ.items() if name not in HIDDEN_ENV} | extra_env
    return command, env, str(cwd)


_command, _env, _cwd = _prepare()


# Returns the harness's stdout; raises on a non-zero exit, a spawn error or the agent timeout.
def run_harness(job: Job) -> str:
    assert _command, 'jobs are only accepted when the harness is prepared'
    args = _command(job.prompt)
    log('DEBUG', f'[{job.label}] running {" ".join(args)}')
    try:
        result = subprocess.run(
            args,
            cwd=_cwd,
            env=_env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=agent.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise HarnessError(f'{HARNESS} timed out after {agent.timeout_seconds}s') from error
    if result.stderr:
        log('DEBUG', f'[{job.label}] {HARNESS} stderr:\n{result.stderr}')
    if result.returncode != 0:
        raise HarnessError(f'{HARNESS} exited {result.returncode}: {result.stderr[-STDERR_TAIL_LENGTH:]}')
    return result.stdout.strip()
