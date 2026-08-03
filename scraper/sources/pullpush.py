"""Optional historical Reddit backfill via PullPush (the Pushshift successor).

Two hard limits, both verified against the live service:

1. The index ends around 2025-05-19 — there is no recent data here at all.
2. PullPush rate-limits aggressively and returns, verbatim, "This website does
   not provide free scraping resources for agents." Bulk backfill is not
   something they offer for free.

So this module is **opt-in and best-effort** (`--pullpush`), disabled by
default. On a 429 it raises `RateLimited` and stops rather than retrying, since
retrying is precisely what they've asked callers not to do. The official Reddit
API in `reddit_api.py` is the primary source.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import requests

from .. import config

BASE = "https://api.pullpush.io/reddit/search"
UA = "ead-eta/1.0 (github.com/ead-eta; research on EAD processing times)"
PAGE = 100
PAUSE = 3.0          # deliberately slow; this is someone else's free service
MAX_RETRY = 2


class RateLimited(RuntimeError):
    """PullPush declined the request. Back off entirely; do not retry."""


def _get(kind: str, **params) -> list[dict]:
    url = f"{BASE}/{kind}/"
    params.setdefault("size", PAGE)
    for attempt in range(MAX_RETRY):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=60)
            if r.status_code == 200:
                return r.json().get("data", [])
            if r.status_code == 429:
                raise RateLimited(
                    "PullPush rate limit hit. It does not offer free bulk "
                    "scraping — run with the Reddit API instead, or contact "
                    "them about paid access."
                )
            if r.status_code in (500, 502, 503, 504):
                time.sleep(2 ** attempt * 3)
                continue
            r.raise_for_status()
        except requests.RequestException:
            if attempt == MAX_RETRY - 1:
                raise
            time.sleep(2 ** attempt * 3)
    return []


def coverage_end() -> datetime | None:
    """Newest comment PullPush will serve — i.e. where live scraping must start."""
    rows = _get("comment", subreddit="USCIS", size=1, sort="desc", sort_type="created_utc")
    if not rows:
        return None
    return datetime.fromtimestamp(rows[0]["created_utc"], timezone.utc)


def search_comments(query: str, subreddit: str, after: int, before: int) -> list[dict]:
    """Page backwards through a time window until the window is exhausted."""
    out: list[dict] = []
    cursor = before
    seen: set[str] = set()

    while True:
        batch = _get("comment", subreddit=subreddit, q=query,
                     after=after, before=cursor,
                     sort="desc", sort_type="created_utc")
        fresh = [c for c in batch if c.get("id") not in seen]
        if not fresh:
            break
        for c in fresh:
            seen.add(c["id"])
        out.extend(fresh)

        oldest = min(c["created_utc"] for c in fresh)
        if oldest <= after or len(batch) < PAGE:
            break
        cursor = int(oldest)   # step the window back
        time.sleep(PAUSE)

    return out


def thread_comments(link_id: str) -> list[dict]:
    """Every archived comment under one submission."""
    out: list[dict] = []
    cursor = int(time.time())
    seen: set[str] = set()

    while True:
        batch = _get("comment", link_id=link_id, before=cursor,
                     sort="desc", sort_type="created_utc")
        fresh = [c for c in batch if c.get("id") not in seen]
        if not fresh:
            break
        for c in fresh:
            seen.add(c["id"])
        out.extend(fresh)
        oldest = min(c["created_utc"] for c in fresh)
        if len(batch) < PAGE:
            break
        cursor = int(oldest)
        time.sleep(PAUSE)

    return out


def find_megathreads(subreddit: str, queries: list[str]) -> list[dict]:
    """Discover timeline threads so the crawler survives mods rolling new ones."""
    found: dict[str, dict] = {}
    for q in queries:
        for s in _get("submission", subreddit=subreddit, q=q, size=50,
                      sort="desc", sort_type="created_utc"):
            found[s["id"]] = {
                "id": s["id"],
                "title": s.get("title", ""),
                "created_utc": s.get("created_utc"),
                "num_comments": s.get("num_comments", 0),
                "permalink": s.get("permalink", ""),
            }
        time.sleep(PAUSE)
    return sorted(found.values(), key=lambda s: -(s.get("num_comments") or 0))
