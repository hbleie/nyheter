# Nyheter

A news page built from RSS feeds: image, title and ingress for each article, newest first.
Clicking an article opens it on the publisher's site.

Uses the same feeds as the termkit `newsboat-newspaper.py` script (VG, NRK, E24, TV 2),
but fetches them directly, so newsboat is not required.

## Run

Python 3.9+ and nothing else (standard library only):

```bash
python3 server.py
```

Opens <http://localhost:8765/> in your browser. Options:

| Flag | Description |
|---|---|
| `--port N` | Serve on another port (default 8765) |
| `--no-browser` | Don't open the page on start |

## Feeds

Edit `feeds.txt`, one RSS URL per line (`#` starts a comment). Restart the server to pick up changes.

An optional second column sets a fallback image for items that have none, served from `static/`:

```
https://news.ycombinator.com/rss  /static/hn.svg
```

## How it works

- `server.py` fetches every feed on start and again every 5 minutes, merges the items, removes
  duplicates by URL and sorts by publish time. Images come from `<enclosure>`, `media:content`,
  `media:thumbnail`, VG's `vg:img`, or the first `<img>` in the description.
- `static/index.html` is the page. It loads articles from `/api/articles` with infinite scroll,
  filters by source via `/api/sources`, and checks for new stories every minute
  (shown as a "nye saker" button rather than reshuffling the page under you).
