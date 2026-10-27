"""HTTP bridge server for studio_ui_demo.html"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


class DemoBridgeHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path) if False else None