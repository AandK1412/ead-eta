"""Live Reddit data via the official OAuth API.

Reddit blocks unauthenticated JSON scraping (403 from any datacenter IP), so
this is the supported route for anything newer than PullPush's archive. It uses
a free "script" app — see README for the two-minute setup.

Credentials come from the environment:
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT

If they are absent, `available()` returns False and the build falls back to
archive-only data rather than failing.
"""

from __future__ import annotations

import os

from .. import config

DEFAULT_UA = "script:ead-eta:1.0 (by /u/unknown)"


def available() -> bool:
    return bool(os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET"))


def _client():
    import praw  # imported lazily so archive-only runs need no praw install

    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.getenv("REDDIT_USER_AGENT", DEFAULT_UA),
        check_for_async=False,
    )


def find_megathreads(subreddit: str, queries: list[str], limit: int = 40) -> list[dict]:
    reddit = _client()
    sub = reddit.subreddit(subreddit)
    found: dict[str, dict] = {}

    for q in queries:
        try:
            for s in sub.search(q, sort="new", time_filter="all", limit=limit):
                found[s.id] = {
                    "id": s.id,
                    "title": s.title,
                    "created_utc": s.created_utc,
                    "num_comments": s.num_comments,
                    "permalink": s.permalink,
                }
        except Exception as exc:  # one bad query shouldn't kill the crawl
            print(f"    ! search {subreddit!r} {q!r}: {exc}")

    # Pinned posts are where mods park the current megathread.
    try:
        for s in sub.hot(limit=25):
            if s.stickied:
                found[s.id] = {
                    "id": s.id, "title": s.title, "created_utc": s.created_utc,
                    "num_comments": s.num_comments, "permalink": s.permalink,
                }
    except Exception as exc:
        print(f"    ! hot {subreddit!r}: {exc}")

    return sorted(found.values(), key=lambda s: -(s.get("num_comments") or 0))


def thread_comments(thread_id: str, max_comments: int = 8000) -> list[dict]:
    """Flatten a whole comment tree, expanding 'load more' stubs."""
    reddit = _client()
    sub = reddit.submission(id=thread_id)
    try:
        sub.comments.replace_more(limit=None)
    except Exception as exc:
        print(f"    ! replace_more on {thread_id}: {exc}")

    out = []
    for c in sub.comments.list()[:max_comments]:
        body = getattr(c, "body", None)
        if not body:
            continue
        out.append({
            "id": c.id,
            "body": body,
            "created_utc": c.created_utc,
            "permalink": getattr(c, "permalink", ""),
            "link_id": f"t3_{thread_id}",
            "thread_title": sub.title,
        })
    return out
