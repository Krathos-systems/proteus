import os
import sys
from typing import Literal

# Syslog severities: lower is more severe.
type LogLevel = Literal['DEBUG', 'ERROR', 'INFORMATION', 'WARNING']
LEVELS: dict[str, int] = {'DEBUG': 7, 'ERROR': 3, 'INFORMATION': 6, 'WARNING': 4}

REDACTED = '***'
# Values shorter than this are not redacted, so short placeholders do not mangle every log line.
MIN_SECRET_LENGTH = 4

_configured = os.environ.get('LOG_LEVEL', 'INFORMATION').upper()
LOG_LEVEL = _configured if _configured in LEVELS else 'INFORMATION'
APP_NAME = os.environ.get('APP_NAME', 'PROTEUS')

_secrets: set[str] = set()


# Secret values are masked in every log line, whatever logged them (e.g. copilot stderr).
def register_secrets(values: list[str | None]) -> None:
    _secrets.update(value for value in values if value and len(value) >= MIN_SECRET_LENGTH)


def _redact(message: str) -> str:
    for secret in _secrets:
        message = message.replace(secret, REDACTED)
    return message


def log(level: LogLevel, message: str) -> None:
    if LEVELS[level] > LEVELS[LOG_LEVEL]:
        return
    stream = sys.stderr if LEVELS[level] <= LEVELS['WARNING'] else sys.stdout
    stream.write(f'[{level}] {_redact(message)}\n')
    stream.flush()
