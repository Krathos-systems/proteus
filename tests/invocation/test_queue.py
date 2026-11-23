import re
import time

from tests.conftest import StartServer, wait_for

MIN_GAP_SECONDS = 0.35


def test_jobs_run_one_at_a_time_in_order(start_server: StartServer) -> None:
    server = start_server(copilot='sleep 0.4')
    for key in ['DO-1', 'DO-2', 'DO-3']:
        assert server.webhook({'key': key}).status == 202
    wait_for(lambda: server.output.count('job finished') == 3, timeout=10)
    calls = server.calls()
    assert [re.search(r'DO-\d', call['args'][1])[0] for call in calls] == ['DO-1', 'DO-2', 'DO-3']  # type: ignore[index]
    assert calls[1]['at'] - calls[0]['at'] >= MIN_GAP_SECONDS, 'second job must wait for the first'
    assert calls[2]['at'] - calls[1]['at'] >= MIN_GAP_SECONDS, 'third job must wait for the second'


def test_webhook_answers_immediately_while_a_job_is_running(start_server: StartServer) -> None:
    server = start_server(copilot='sleep 1')
    server.webhook({'key': 'DO-1'})
    started = time.monotonic()
    assert server.webhook({'key': 'DO-2'}).status == 202
    assert time.monotonic() - started < 0.5


def test_queue_accepts_new_jobs_after_draining(start_server: StartServer) -> None:
    server = start_server()
    server.webhook({'key': 'DO-1'})
    wait_for(lambda: '[job 1] job finished' in server.output)
    server.webhook({'key': 'DO-2'})
    wait_for(lambda: '[job 2] job finished' in server.output)


# failure handling ("$2" is copilot's prompt)


def test_failing_copilot_is_logged_and_the_queue_keeps_going(start_server: StartServer) -> None:
    server = start_server(copilot='case "$2" in *DO-1*) echo boom >&2; exit 3;; esac; echo ok')
    server.webhook({'key': 'DO-1'})
    server.webhook({'key': 'DO-2'})
    wait_for(lambda: '[job 2] job finished' in server.output)
    assert '[job 1] failed: copilot exited 3: boom' in server.output
    assert server.request('/ai/test/healthcheck').status == 200


def test_missing_copilot_binary_is_logged_and_does_not_crash(start_server: StartServer) -> None:
    server = start_server()
    (server.bin_dir / 'copilot').unlink()
    server.webhook({'key': 'DO-1'})
    wait_for(lambda: '[job 1] failed' in server.output)
    assert server.request('/ai/test/healthcheck').status == 200


def test_job_exceeding_timeout_is_killed_and_the_next_job_runs(start_server: StartServer) -> None:
    server = start_server({'timeoutSeconds': 0.5}, copilot='case "$2" in *DO-1*) exec sleep 30;; esac; echo ok')
    server.webhook({'key': 'DO-1'})
    server.webhook({'key': 'DO-2'})
    wait_for(lambda: '[job 2] job finished' in server.output, timeout=8)
    assert '[job 1] failed: copilot timed out after 0.5s' in server.output
