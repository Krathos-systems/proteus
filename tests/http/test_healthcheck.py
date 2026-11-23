from tests.conftest import StartServer


def test_prefixed_healthcheck_returns_200_ok(start_server: StartServer) -> None:
    response = start_server().request('/ai/test/healthcheck')
    assert (response.status, response.text) == (200, 'ok')


def test_unprefixed_healthcheck_and_query_strings(start_server: StartServer) -> None:
    server = start_server()
    assert server.request('/healthcheck').status == 200
    assert server.request('/ai/test/healthcheck?x=1').status == 200


def test_other_paths_foreign_prefixes_and_wrong_methods_return_404(start_server: StartServer) -> None:
    server = start_server()
    assert server.request('/').status == 404
    assert server.request('/ai/other/healthcheck').status == 404
    assert server.request('/ai/testing/healthcheck').status == 404
    assert server.request('/ai/other/webhook', method='POST', body=b'').status == 404
    assert server.request('/ai/test/webhook').status == 404
    assert server.request('/ai/test/healthcheck', method='POST', body=b'').status == 404


def test_path_prefix_env_overrides_the_agent_prefix_and_strips_trailing_slashes(start_server: StartServer) -> None:
    server = start_server(env={'PATH_PREFIX': '/custom/'})
    assert server.request('/custom/healthcheck').status == 200
    assert server.request('/ai/test/healthcheck').status == 404
