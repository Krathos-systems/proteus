import sys


def serve() -> None:
    from runner.config import DRY_RUN, HARNESS, PORT, PREFIX, agent, config_errors
    from runner.logger import APP_NAME, LOG_LEVEL, log
    from runner.server import create_server
    from runner.worker import start_worker

    server = create_server(PORT)
    if config_errors:
        log('ERROR', f'CRITICAL: webhook disabled, {"; ".join(config_errors)}')
    start_worker()
    details = [
        f'prefix "{PREFIX}"',
        f'agent {agent.name or "unconfigured"}',
        f'harness {HARNESS or "unset"}',
        f'dry run {str(DRY_RUN).lower()}',
        f'log level {LOG_LEVEL}',
        *(['webhook DISABLED'] if config_errors else []),
    ]
    log('INFORMATION', f'{APP_NAME} started on port {PORT} ({", ".join(details)})')
    server.serve_forever()


def main(argv: list[str]) -> int:
    if len(argv) >= 1 and argv[0] == 'new':
        from runner.scaffold import main as scaffold

        return scaffold(argv[1:])
    if argv:
        print(
            'usage: python -m runner            start the webhook server\n'
            '       python -m runner new NAME   create agents/NAME from the example agent',
            file=sys.stderr,
        )
        return 2
    serve()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
