#!/usr/bin/env python3
"""Nyheter: a news page built from RSS feeds, with images, titles and ingresses.

Serves the page locally. The feeds are fetched on request and cached for
feeds.CACHE_SECONDS, the same as on Vercel (api/articles.py).
"""

import argparse
import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from feeds import get_articles

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".css": "text/css",
    ".js": "text/javascript",
}
DEFAULT_PORT = 8765


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/articles.json":
            body = json.dumps(get_articles(), ensure_ascii=False).encode()
            self.send(200, "application/json; charset=utf-8", body)
        elif not self.send_public(path.lstrip("/") or "index.html"):
            self.send(404, "text/plain", b"Not found")

    def send_public(self, name):
        # Flat directory only, so no path can escape it
        content_type = CONTENT_TYPES.get(os.path.splitext(name)[1])
        path = os.path.join(PUBLIC_DIR, name)
        if "/" in name or not content_type or not os.path.isfile(path):
            return False
        with open(path, "rb") as f:
            self.send(200, content_type, f.read())
        return True

    def send(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="Serve a news page built from RSS feeds.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true", help="don't open the page on start")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://localhost:{args.port}/"
    print(f"Serving on {url}  (Ctrl-C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
