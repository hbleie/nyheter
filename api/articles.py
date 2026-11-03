"""Vercel serverless function behind /articles.json (see vercel.json)."""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feeds import CACHE_SECONDS, get_articles  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        data = get_articles()
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200 if data["articles"] else 502)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # Vercel's CDN keeps the result for a minute, so the feeds are fetched
        # at most once a minute however many people refresh
        if data["articles"]:
            self.send_header("Cache-Control", f"public, max-age=0, s-maxage={CACHE_SECONDS}")
        else:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
