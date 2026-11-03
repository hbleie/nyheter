#!/usr/bin/env python3
"""Nyheter: a news page built from RSS feeds, with images, titles and ingresses.

Standard library only. Feeds are listed in feeds.txt (one URL per line) and
refreshed in the background every REFRESH_INTERVAL seconds.
"""

import argparse
import html
import json
import os
import re
import threading
import time
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
FEEDS_FILE = os.path.join(ROOT, "feeds.txt")
STATIC_DIR = os.path.join(ROOT, "static")
STATIC_TYPES = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".css": "text/css", ".js": "text/javascript"}
PAGE = os.path.join(STATIC_DIR, "index.html")
REFRESH_INTERVAL = 300
ARTICLES_PER_PAGE = 30
DEFAULT_PORT = 8765
USER_AGENT = "Mozilla/5.0 (Nyheter RSS reader)"

NS = {
    "media": "http://search.yahoo.com/mrss/",
    "vg": "http://www.vg.no/namespace",
    "dc": "http://purl.org/dc/elements/1.1/",
}
IMG_TAG = re.compile(r"""<img[^>]+src=["']([^"']+)""", re.I)
LINK_ONLY = re.compile(r"\s*<a\s[^>]*>[^<]*</a>\s*", re.I)

articles = []
articles_lock = threading.Lock()


def strip_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def http_url(url):
    url = (url or "").strip()
    return url if url.startswith(("http://", "https://")) else None


def read_feeds():
    """Return (url, fallback_image) pairs; the image column is optional."""
    feeds = []
    with open(FEEDS_FILE) as f:
        for line in f:
            parts = line.split()
            if parts and not parts[0].startswith("#"):
                feeds.append((parts[0], parts[1] if len(parts) > 1 else None))
    return feeds


def parse_date(text):
    if not text:
        return 0
    try:
        return int(parsedate_to_datetime(text).timestamp())
    except (TypeError, ValueError):
        pass
    try:
        return int(datetime.fromisoformat(text.strip().replace("Z", "+00:00")).timestamp())
    except ValueError:
        return 0


def find_image(item, description):
    for enc in item.findall("enclosure"):
        if enc.get("type", "").startswith(("image/", "img/")):
            return http_url(enc.get("url"))
    for media in item.findall("media:content", NS):
        if media.get("medium") == "image" or media.get("type", "").startswith("image/"):
            return http_url(media.get("url"))
    for path in ("media:thumbnail", "media:group/media:content"):
        media = item.find(path, NS)
        if media is not None:
            return http_url(media.get("url"))
    vg_img = item.findtext("vg:img", namespaces=NS)
    if vg_img:
        return http_url(vg_img)
    match = IMG_TAG.search(description or "")
    return http_url(html.unescape(match.group(1))) if match else None


def fetch_feed(url, fallback_image=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as res:
        root = ET.fromstring(res.read())

    channel = root.find("channel")
    if channel is None:
        return []
    source = strip_html(channel.findtext("title")) or urlparse(url).hostname

    items = []
    for item in channel.findall("item"):
        link = http_url(item.findtext("link"))
        if not link:
            continue
        description = item.findtext("description") or ""
        # Hacker News descriptions are just a "Comments" link, not an ingress
        ingress = "" if LINK_ONLY.fullmatch(description) else strip_html(description)
        items.append({
            "title": strip_html(item.findtext("title")),
            "ingress": ingress,
            "source": source,
            "published": parse_date(item.findtext("pubDate") or item.findtext("dc:date", namespaces=NS)),
            "url": link,
            "image": find_image(item, description) or fallback_image,
        })
    return items


def refresh():
    global articles
    feeds = read_feeds()
    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for url, future in [(u, pool.submit(fetch_feed, u, img)) for u, img in feeds]:
            try:
                results.extend(future.result())
            except Exception as e:
                print(f"Failed to fetch {url}: {e}")

    # Same story can appear in several feeds from one site (e.g. TV 2 news/sport)
    unique = {}
    for article in results:
        unique.setdefault(article["url"], article)
    fresh = sorted(unique.values(), key=lambda a: a["published"], reverse=True)

    if fresh:
        with articles_lock:
            articles = fresh


def refresh_loop():
    while True:
        time.sleep(REFRESH_INTERVAL)
        refresh()


def get_articles(offset=0, limit=ARTICLES_PER_PAGE, source=None):
    with articles_lock:
        selected = [a for a in articles if not source or a["source"] == source]
    return selected[offset:offset + limit]


def get_sources():
    with articles_lock:
        return sorted({a["source"] for a in articles})


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        try:
            if url.path == "/":
                with open(PAGE, "rb") as f:
                    self.send(200, "text/html; charset=utf-8", f.read())
            elif url.path == "/api/articles":
                offset = max(0, int(query.get("offset", ["0"])[0]))
                source = query.get("source", [None])[0]
                self.send_json({"articles": get_articles(offset, source=source)})
            elif url.path == "/api/sources":
                self.send_json({"sources": get_sources()})
            elif url.path.startswith("/static/") and self.send_static(url.path[len("/static/"):]):
                pass
            else:
                self.send(404, "text/plain", b"Not found")
        except ValueError:
            self.send(400, "text/plain", b"Bad request")

    def send_static(self, name):
        # Flat directory only, so no path can escape it
        content_type = STATIC_TYPES.get(os.path.splitext(name)[1])
        path = os.path.join(STATIC_DIR, name)
        if "/" in name or not content_type or not os.path.isfile(path):
            return False
        with open(path, "rb") as f:
            self.send(200, content_type, f.read())
        return True

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send(status, "application/json; charset=utf-8", body)

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

    print("Fetching feeds …")
    refresh()
    print(f"Loaded {len(articles)} articles")
    threading.Thread(target=refresh_loop, daemon=True).start()

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
