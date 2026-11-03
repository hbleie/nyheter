# Nyheter

A news page built from RSS feeds: image, title and ingress for each article, newest first.
Clicking an article opens it on the publisher's site.

Uses the same feeds as the termkit `newsboat-newspaper.py` script (VG, NRK, E24, TV 2,
Hacker News), but fetches them directly, so newsboat is not required.

## Run locally

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

Edit `feeds.txt`, one RSS URL per line (`#` starts a comment).

An optional second column sets a fallback image for items that have none, a file in `public/`:

```
https://news.ycombinator.com/rss  hn.svg
```

## Hosting on Vercel

The repo deploys to Vercel as is, on the free Hobby plan:

1. On <https://vercel.com>, sign in with GitHub and choose **Add New → Project**.
2. Import `hbleie/nyheter` and press **Deploy**. Leave the settings as they are; `vercel.json`
   sets them.

Every push to `main` deploys again. The feeds are fetched when someone opens the page, so there
is no schedule to maintain.

## How it works

- `feeds.py` fetches every feed in parallel, merges the items, removes duplicates by URL and
  sorts by publish time. Images come from `<enclosure>`, `media:content`, `media:thumbnail`,
  VG's `vg:img`, or the first `<img>` in the description. Results are reused for 60 seconds.
- `/articles.json` returns the articles. Locally `server.py` serves it; on Vercel it is the
  Python function `api/articles.py`, and Vercel's CDN caches it for 60 seconds, so a refresh
  shows news at most a minute old.
- `public/index.html` is the page. It loads `articles.json`, filters by source and renders
  30 articles at a time as you scroll, and checks for new stories every minute (shown as a
  "nye saker" button rather than reshuffling the page under you).
