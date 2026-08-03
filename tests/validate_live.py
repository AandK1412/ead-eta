"""Pull real megathread comments and report how well the parser does on them.

Run: python -m tests.validate_live
Prints a hit rate plus samples of what was parsed and what was missed, so
regressions in the regexes are visible against actual posts rather than fixtures.
"""

from __future__ import annotations

import json
import os
import sys
import time

from scraper import parse
from scraper.sources import pullpush

THREAD = "t3_1i6230k"  # "2025 OPT processing timeline"
CACHE = os.path.join("data", "raw", f"validate_{THREAD}.json")


def load_comments() -> list[dict]:
    """Cache locally — PullPush is a free service and rate-limits fast."""
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as fh:
            comments = json.load(fh)
        print(f"using cached {CACHE} ({len(comments)} comments)")
        return comments

    for attempt in range(4):
        print(f"fetching {THREAD} from PullPush (attempt {attempt + 1}) ...")
        comments = pullpush.thread_comments(THREAD)
        if comments:
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            with open(CACHE, "w", encoding="utf-8") as fh:
                json.dump(comments, fh)
            return comments
        time.sleep(10 * (attempt + 1))

    print("PullPush returned nothing (rate limited?) — try again shortly")
    return []


def main() -> int:
    comments = load_comments()
    print(f"  {len(comments)} comments\n")
    if not comments:
        return 1

    parsed, missed = [], []
    for c in comments:
        rec = parse.parse_comment(
            c.get("body", ""), c["created_utc"], c["id"],
            c.get("permalink", ""), source="pullpush",
        )
        (parsed if rec else missed).append((c, rec))

    total = len(comments)
    ok = len(parsed)
    approved = sum(1 for _, r in parsed if r.event)
    print(f"parsed   : {ok}/{total} ({ok / max(total,1):.0%})")
    print(f"  approvals (events)  : {approved}")
    print(f"  still waiting (cens): {ok - approved}\n")

    print("--- sample parsed ---")
    for _, r in parsed[:8]:
        print(f"  {r.receipt} -> {r.approved or '(waiting)'}  "
              f"days={r.days if r.days is not None else r.censored_days}"
              f"{'' if r.event else '+'}  cat={r.category}  pp={r.premium}")

    print("\n--- sample missed ---")
    for c, _ in missed[:6]:
        body = " ".join(c.get("body", "").split())[:130]
        print(f"  {body}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
