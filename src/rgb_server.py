"""
Lightweight HTTP server that receives RGB color updates from SignalRGB
(or any compatible app) and dispatches them to the MacroPad API.

Listens on 127.0.0.1:7237  — loopback only, not exposed to the network.
"""
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

log = logging.getLogger(__name__)
PORT = 7237


class _Handler(BaseHTTPRequestHandler):
    _callback = None

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        if self.path == '/status':
            body = b'{"ok":true,"name":"MacroPad","leds":40}'
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != '/rgb':
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            body   = self.rfile.read(length)
            data   = json.loads(body)
            leds   = data.get('leds', [])   # list of [r, g, b]
            if self._callback:
                self._callback(leds)
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'ok')
        except Exception as e:
            log.debug(f'RGB handler error: {e}')
            self.send_response(400)
            self.end_headers()

    def log_message(self, *_):
        pass   # silence default request logging


def start(callback):
    """Start the RGB HTTP server in a daemon thread. Returns the HTTPServer instance."""
    _Handler._callback = callback
    server = HTTPServer(('127.0.0.1', PORT), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info(f'RGB server listening on 127.0.0.1:{PORT}')
    return server
