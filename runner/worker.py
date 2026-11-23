import queue
import threading
import time

from runner.config import DRY_RUN
from runner.job import Job
from runner.logger import log
from runner.run import run_harness

# One run at a time keeps cost and load predictable.
_pending: queue.SimpleQueue[Job] = queue.SimpleQueue()


def _run_job(job: Job) -> None:
    label = job.label
    started = time.monotonic()
    log('INFORMATION', f'[{label}] job started')
    try:
        out = run_harness(job)
    except Exception as error:  # noqa: BLE001 - a failed job must never stop the worker
        log('ERROR', f'[{label}] failed: {error}')
        return
    log('INFORMATION', f'[{label}] job finished in {round(time.monotonic() - started)}s')
    log('INFORMATION' if DRY_RUN else 'DEBUG', f'[{label}] {"dry run result" if DRY_RUN else "result"}:\n{out}')


def _drain() -> None:
    while True:
        _run_job(_pending.get())


def start_worker() -> None:
    threading.Thread(target=_drain, daemon=True, name='worker').start()


def enqueue(job: Job) -> None:
    _pending.put(job)
