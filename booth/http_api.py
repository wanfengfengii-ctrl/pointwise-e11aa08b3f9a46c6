import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sqlite3

from booth.application import handle_operation, initialize_application


def _invalid_constant(value):
    raise ValueError(f'invalid JSON number {value}')


def build_handler(database):
    class TheatreHandler(BaseHTTPRequestHandler):
        def _respond(self, status, document):
            encoded = json.dumps(document, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if self.path == '/health':
                self._respond(200, {'status': 'ready'})
            else:
                self._respond(404, {'error': 'operation_not_found'})

        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length <= 0:
                    raise ValueError('JSON body is required')
                body = self.rfile.read(length).decode('utf-8')
                payload = json.loads(body, parse_constant=_invalid_constant)
            except (ValueError, RecursionError):
                self._respond(400, {'error': 'invalid_json_body'})
                return

            operation = self.path.removeprefix('/')
            try:
                status, document = handle_operation(database, operation, payload)
            except (sqlite3.Error, RuntimeError) as error:
                self.log_error('Request failed: %s', error)
                status, document = 500, {'error': 'storage_or_state_error'}
            self._respond(status, document)

        def log_request(self, code='-', size='-'):
            pass

    return TheatreHandler


def serve(database, port: int = 8000) -> ThreadingHTTPServer:
    initialize_application(database)
    return ThreadingHTTPServer(('127.0.0.1', port), build_handler(database))


def main() -> None:
    parser = argparse.ArgumentParser(description='Local audio-description screening service')
    parser.add_argument('--database', required=True)
    parser.add_argument('--host', choices=('127.0.0.1',), default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    options = parser.parse_args()
    with serve(options.database, options.port) as server:
        print(f'Listening on http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
