import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


class _SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        # silence default logging to stderr during tests
        return


@pytest.fixture(scope="session", autouse=False)
def http_server():
    server = HTTPServer(("127.0.0.1", 8081), _SimpleHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield
    finally:
        server.shutdown()
        thread.join(timeout=1)
