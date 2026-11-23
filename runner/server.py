import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from runner.config import PREFIX, WEBHOOK_SECRET, config_errors
from runner.job import BadRequestError, parse_job
from runner.logger import log
from runner.worker import enqueue

MAX_BODY_BYTES = 64 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = 'proteus'
    sys_version = ''

    def _send(self, status: int, body: str = '') -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _path(self) -> tuple[str, str | None]:
        url = self.path.split('?', 1)[0]
        return url, url[len(PREFIX) :] if url.startswith(f'{PREFIX}/') else None

    def do_GET(self) -> None:
        url, path = self._path()
        # The unprefixed healthcheck is for the Docker HEALTHCHECK inside the container.
        if path == '/healthcheck' or url == '/healthcheck':
            self._send(200, 'ok')
        else:
            self._send(404)

    def do_POST(self) -> None:
        _, path = self._path()
        if path != '/webhook':
            self._send(404)
            return
        try:
            self._handle_webhook()
        except Exception as error:  # noqa: BLE001 - answer 500 instead of dropping the connection
            log('ERROR', f'webhook error: {error}')
            self._send(500)

    def _handle_webhook(self) -> None:
        if config_errors:
            self._send(503, 'not configured')
            return
        given = self.headers.get('X-Webhook-Secret', '').encode()
        if not hmac.compare_digest(given, WEBHOOK_SECRET.encode()):
            log('DEBUG', 'webhook rejected: invalid secret')
            self._send(401)
            return
        try:
            length = int(self.headers.get('Content-Length') or 0)
            if length > MAX_BODY_BYTES:
                self.close_connection = True
                raise BadRequestError('payload too large')
            job = parse_job(self.rfile.read(length))
        except BadRequestError as error:
            log('DEBUG', f'webhook rejected: {error}')
            self._send(400, str(error))
            return
        except ValueError:
            self._send(400, 'bad content-length')
            return
        log('DEBUG', f'webhook accepted: {job.label}')
        enqueue(job)
        self._send(202, 'accepted')

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - signature of the base class
        pass  # access logs are off, like the nginx proxy before


def create_server(port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(('', port), Handler)
