"""HTTP bridge server for studio_ui_demo.html"""

from __future__ import annotations

from http.server import SimpleHTTPRequestHandler
from urllib.parse import urlparse


class DemoBridgeHandler(SimpleHTTPRequestHandler):
    """Custom request handler for studio UI preview bridge."""

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            return
        super().do_GET()
