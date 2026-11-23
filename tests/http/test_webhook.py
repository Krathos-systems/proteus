from typing import Any

from tests.conftest import StartServer, wait_for


def test_missing_or_wrong_secret_returns_401_and_never_runs_the_harness(start_server: StartServer) -> None:
    server = start_server()
    assert server.webhook({'key': 'DO-1'}, secret=None).status == 401
    for secret in ['wrong', 's3creT', '']:
        assert server.webhook({'key': 'DO-1'}, secret=secret).status == 401
    # Authentication is checked before the body is parsed.
    assert server.webhook('not json', raw=True, secret='wrong').status == 401
    assert server.calls() == []


BAD_PAYLOADS: list[tuple[str, Any, str, bool]] = [
    ('invalid json', '{nope', 'bad json', True),
    ('null body', None, 'body must be a JSON object', False),
    ('array body', ['DO-1'], 'body must be a JSON object', False),
    ('missing required field', {}, 'key required', False),
    ('lowercase key', {'key': 'do-1'}, 'invalid key', False),
    ('key with injection', {'key': 'DO-1; rm -rf /'}, 'invalid key', False),
    ('key with trailing newline', {'key': 'DO-1\n'}, 'invalid key', False),
    ('numeric key', {'key': 123}, 'invalid key', False),
    ('optional field breaking its pattern', {'key': 'DO-1', 'summary': 'a\nb'}, 'invalid summary', False),
    ('optional field too long', {'key': 'DO-1', 'summary': 'x' * 201}, 'invalid summary', False),
    ('optional field not a string', {'key': 'DO-1', 'summary': ['x']}, 'invalid summary', False),
]


def test_bad_payloads_are_rejected_with_400_and_never_run_the_harness(start_server: StartServer) -> None:
    server = start_server()
    for name, body, message, raw in BAD_PAYLOADS:
        response = server.webhook(body, raw=raw)
        assert (response.status, response.text) == (400, message), name
    assert server.webhook({'key': 'DO-1', 'summary': 'x' * 70 * 1024}).status == 400
    assert server.calls() == []


def test_valid_payloads_are_accepted_and_unknown_fields_ignored(start_server: StartServer) -> None:
    server = start_server()
    assert server.webhook({'key': 'DO-1'}).status == 202
    assert server.webhook({'key': 'A1-9', 'summary': 'a summary', 'extra': {'ignored': True}}).status == 202
    wait_for(lambda: len(server.calls()) == 2)
    calls = server.calls()
    assert 'Use the test-skill skill for issue DO-1 ().' in calls[0]['args'][1]
    assert 'issue A1-9 (a summary).' in calls[1]['args'][1]
    assert 'ignored' not in calls[1]['args'][1]
