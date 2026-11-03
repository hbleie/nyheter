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
| `--build DIR` | Write a static copy of the site to `DIR` and exit |

## Feeds

Edit `feeds.txt`, one RSS URL per line (`#` starts a comment). Restart the server to pick up changes.

An optional second column sets a fallback image for items that have none, served from `static/`:

```
https://news.ycombinator.com/rss  static/hn.svg
```

## Hosting on GitHub Pages

`.github/workflows/pages.yml` runs `python3 server.py --build _site` on every push to `main`
and every 15 minutes, and deploys the result to GitHub Pages. To turn it on:

1. Make the repo public (Pages is not free for private repos).
2. Settings → Pages → Source: **GitHub Actions**.
3. Run the workflow once (Actions → Deploy to GitHub Pages → Run workflow), or push.

GitHub disables scheduled workflows after 60 days without commits in the repo; re-enable it
in the Actions tab if the page stops updating.

## How it works

- `server.py` fetches every feed, merges the items, removes duplicates by URL and sorts by
  publish time. Images come from `<enclosure>`, `media:content`, `media:thumbnail`, VG's
  `vg:img`, or the first `<img>` in the description. Locally it serves the result as
  `/articles.json` and refreshes every 5 minutes; with `--build DIR` it writes the page,
  `articles.json` and `static/` to `DIR` instead.
- `static/index.html` is the page. It loads `articles.json`, filters by source and renders
  30 articles at a time as you scroll, and checks for new stories every minute (shown as a
  "nye saker" button rather than reshuffling the page under you).
