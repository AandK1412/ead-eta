"""Recompute the figures in VALIDATION.md and compare them to external reports.

    python -m tests.cross_reference

Reads docs/data/official.json (no network). External benchmarks are transcribed
constants with a date attached — they come from law-firm and tracker blogs, not
an API, so they need re-checking by hand when the quarter rolls.
"""

from __future__ import annotations

import json
import os
import sys

OFFICIAL = os.path.join("docs", "data", "official.json")

# Independently reported, February 2026. See VALIDATION.md for sources.
EXTERNAL = {
    "as_of": "2026-02",
    "pending": 1_780_000,
    "pending_over_6_months": 1_180_000,
    "avg_processing_months": 4.8,
    "prior_summer_low_months": 2.5,
    "category_ranges": {
        "OPT": (2, 5), "H-4": (6, 12), "adjustment of status": (3, 8), "F-1": (4.5, 4.5),
    },
}


def main() -> int:
    if not os.path.exists(OFFICIAL):
        print(f"missing {OFFICIAL} — run `python -m scraper.build` first")
        return 1

    with open(OFFICIAL, encoding="utf-8") as fh:
        data = json.load(fh)

    buckets = data.get("buckets") or []
    if not buckets:
        print("official.json has no buckets")
        return 1

    pending = sum(b["pending"] for b in buckets)
    backlog = sum(b.get("net_backlog") or 0 for b in buckets)
    received = sum(b["received"] for b in buckets)
    completed = sum(b["completions"] for b in buckets)
    w_published = sum(b["published_months"] * b["completions"] for b in buckets) / completed
    w_implied = sum(b["implied_months"] * b["pending"] for b in buckets) / pending

    print(f"OURS  ({data.get('period')})")
    print(f"  pending                    {pending:>12,}")
    print(f"  past USCIS target          {backlog:>12,}  ({backlog / pending:.1%})")
    print(f"  received / completed       {received:>12,} / {completed:,}"
          f"   inflow {received / completed:.2f}x")
    print(f"  published (completion-wtd) {w_published:>12.1f} months")
    print(f"  implied   (pending-wtd)    {w_implied:>12.1f} months")

    ext = EXTERNAL
    print(f"\nEXTERNAL ({ext['as_of']})")
    print(f"  pending                    {ext['pending']:>12,}")
    print(f"  waiting > 6 months         {ext['pending_over_6_months']:>12,}"
          f"  ({ext['pending_over_6_months'] / ext['pending']:.1%})")
    print(f"  average processing time    {ext['avg_processing_months']:>12.1f} months")

    print("\nCHECKS")
    checks: list[tuple[bool, str]] = []

    # Volume: same order of magnitude, moving the same way.
    ratio = ext["pending"] / pending
    checks.append((0.85 <= ratio <= 1.25,
                   f"pending within 25% of reported ({ratio:.2f}x)"))

    # Backlog share: different definitions, so allow a wide band.
    ours_share = backlog / pending
    theirs_share = ext["pending_over_6_months"] / ext["pending"]
    checks.append((abs(ours_share - theirs_share) < 0.15,
                   f"backlog share {ours_share:.1%} vs reported {theirs_share:.1%}"))

    # The core claim: a published median under 5 months is incompatible with
    # two-thirds of the queue already past 6 months.
    checks.append((theirs_share > 0.5 and ext["avg_processing_months"] < 6,
                   f"published {ext['avg_processing_months']}mo vs {theirs_share:.0%} "
                   f"past 6mo — published figure understates the queue"))

    # Little's Law is expected to overshoot; flag it explicitly rather than
    # letting it look like a validated point estimate.
    overshoot = w_implied / ext["avg_processing_months"]
    checks.append((overshoot > 1.5,
                   f"implied overshoots reported average by {overshoot:.1f}x "
                   f"— upper bound only, not a point estimate"))

    for ok, msg in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")

    # Growth consistency: the known open discrepancy.
    net_per_month = (received - completed) / 3
    implied_growth = (ext["pending"] - pending) / 2
    print(f"\nOPEN DISCREPANCY")
    print(f"  our flows imply       {net_per_month:>+12,.0f} pending/month")
    print(f"  reported change needs {implied_growth:>+12,.0f} pending/month")
    print("  -> flows likely shifted after Dec 2025, or the external figure uses a")
    print("     different basis. Re-check when FY2026 Q2 publishes.")

    return 0 if all(ok for ok, _ in checks) else 2


if __name__ == "__main__":
    sys.exit(main())
