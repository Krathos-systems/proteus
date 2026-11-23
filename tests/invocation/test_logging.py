from tests.conftest import StartServer, wait_for


def test_dry_run_result_is_logged_at_information_live_result_at_debug(start_server: StartServer) -> None:
    dry = start_server(copilot='echo "the comment"', env={'DRY_RUN': 'true'})
    live = start_server(copilot='echo "the comment"', env={'DRY_RUN': 'false'})
    dry.webhook({'key': 'DO-1'})
    live.webhook({'key': 'DO-1'})
    wait_for(lambda: 'job finished' in dry.output and 'job finished' in live.output)
    assert 'dry run result:\nthe comment' in dry.output
    assert 'the comment' not in live.output


def test_debug_level_logs_rejected_webhooks_and_the_command(start_server: StartServer) -> None:
    server = start_server(env={'LOG_LEVEL': 'DEBUG'})
    server.webhook({'key': 'DO-1'}, secret='bad')
    wait_for(lambda: 'invalid secret' in server.output)
    server.webhook({'key': 'DO-1'})
    wait_for(lambda: '[job 1] running copilot -p' in server.output)


def test_default_level_hides_debug_lines(start_server: StartServer) -> None:
    server = start_server()
    server.webhook({'key': 'DO-1'})
    wait_for(lambda: 'job finished' in server.output)
    assert 'running copilot' not in server.output
    assert 'webhook accepted' not in server.output


def test_secret_looking_env_values_are_redacted_from_every_log_line(start_server: StartServer) -> None:
    server = start_server(
        copilot='echo "token s3cret auth dGVzdA== key sk-live-123 pass" >&2; exit 1',
        env={'LOG_LEVEL': 'DEBUG', 'OPENAI_API_KEY': 'sk-live-123'},
    )
    server.webhook({'key': 'DO-1'})
    wait_for(lambda: '[job 1] failed' in server.output)
    assert 'token *** auth *** key *** pass' in server.output
    for secret in ['s3cret', 'dGVzdA==', 'sk-live-123']:
        assert secret not in server.output
