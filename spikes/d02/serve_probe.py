"""Bind the isolated probe server before declaring readiness."""
import http.server
import sys
from pathlib import Path

with http.server.ThreadingHTTPServer(('127.0.0.1', 8765), http.server.SimpleHTTPRequestHandler) as server:
    Path(sys.argv[1]).write_text('ready\n')
    server.serve_forever()
