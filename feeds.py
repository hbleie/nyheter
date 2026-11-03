"""Fetch the RSS feeds in feeds.txt and turn them into articles.

Standard library only. Shared by server.py (local) and api/articles.py (Vercel).
"""

import html
import os
import re
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

FEEDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feeds.txt")
CACHE_SECONDS = 60
FETCH_TIMEOUT = 8
USER_AGENT = "Mozilla/5.0 (Nyheter RSS reader)"

NS = {
    "media": "http://search.yahoo.com/mrss/",
    "vg": "http://www.vg.no/namespace",
    "dc": "http://purl.org/dc/elements/1.1/",
}
IMG_TAG = re.compile(r"""<img[^>]+src=["']([^"']+)""", re.I)
LINK_ONLY = re.compile(r"\s*<a\s[^>]*>[^<]*</a>\s*", re.I)

_cache = {"articles": [], "updated": 0}
_cache_lock = threading.Lock()


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
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as res:
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


def fetch_all():
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
    return sorted(unique.values(), key=lambda a: a["published"], reverse=True)


def get_articles():
    """Return {"articles", "updated"}, refetching the feeds when older than CACHE_SECONDS.

    If every feed fails, the previous articles are kept.
    """
    with _cache_lock:
        if time.time() - _cache["updated"] >= CACHE_SECONDS:
            fresh = fetch_all()
            if fresh:
                _cache["articles"] = fresh
                _cache["updated"] = int(time.time())
        return dict(_cache)
