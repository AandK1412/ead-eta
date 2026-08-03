"""Collect -> parse -> dedupe -> emit the JSON the static site reads.

    python -m scraper.build                 # Reddit API (needs credentials)
    python -m scraper.build --pullpush      # also try the historical archive
    python -m scraper.build --demo          # synthetic data, no network

Records are emitted raw (compactly) rather than pre-aggregated, so the front end
can recompute survival curves for any combination of filters the user picks.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone

from . import config, parse, survival
from .sources import pullpush, reddit_api, uscis_bulk, uscis_history, uscis_premium


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def collect_reddit_api(max_threads: int | None = None,
                       save_raw: bool = False) -> list[parse.Record]:
    records: list[parse.Record] = []
    threads: dict[str, dict] = {}
    raw_dump: list[dict] = []

    for sub in config.SUBREDDITS:
        print(f"  discovering threads in r/{sub} ...")
        try:
            for t in reddit_api.find_megathreads(sub, config.MEGATHREAD_QUERIES):
                if t["num_comments"] >= 20:
                    threads[t["id"]] = t
        except Exception as exc:
            print(f"  ! r/{sub}: {exc}")

    for tid in config.SEED_THREAD_IDS:
        threads.setdefault(tid, {"id": tid, "title": "", "num_comments": 0})

    # Busiest threads first, so a truncated run still gets the best data.
    ordered = sorted(threads.items(), key=lambda kv: -(kv[1].get("num_comments") or 0))
    if max_threads:
        ordered = ordered[:max_threads]
    print(f"  {len(threads)} candidate threads; crawling {len(ordered)}")

    for i, (tid, meta) in enumerate(ordered, 1):
        title = (meta.get("title") or "")[:60]
        n = meta.get("num_comments") or 0
        print(f"  [{i}/{len(ordered)}] {tid} ({n} comments) {title}")
        try:
            before = len(records)
            comments = reddit_api.thread_comments(tid)
            for c in comments:
                rec = parse.parse_comment(
                    c["body"], c["created_utc"], c["id"], c.get("permalink", ""),
                    source="reddit", thread_title=c.get("thread_title", ""))
                if rec:
                    records.append(rec)
            got = len(records) - before
            print(f"      {len(comments)} comments -> +{got} records"
                  f" ({got / max(len(comments), 1):.0%})")
            if save_raw:
                raw_dump.extend(comments)
        except Exception as exc:
            print(f"    ! {tid}: {exc}")

    if save_raw and raw_dump:
        os.makedirs(config.RAW_DIR, exist_ok=True)
        path = os.path.join(config.RAW_DIR, "reddit_comments.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(raw_dump, fh)
        print(f"\n  saved {len(raw_dump)} raw comments -> {path}")
        print("  (that file is gitignored; it's for tuning the parser)")

    return records


def collect_pullpush() -> list[parse.Record]:
    records: list[parse.Record] = []
    try:
        end = pullpush.coverage_end()
        print(f"  PullPush coverage ends: {end}")
        for tid in config.SEED_THREAD_IDS:
            for c in pullpush.thread_comments(f"t3_{tid}"):
                rec = parse.parse_comment(
                    c.get("body", ""), c["created_utc"], c["id"],
                    c.get("permalink", ""), source="pullpush")
                if rec:
                    records.append(rec)
    except pullpush.RateLimited as exc:
        print(f"  ! {exc}")
    except Exception as exc:
        print(f"  ! pullpush: {exc}")
    return records


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

def make_demo(n: int = 2600, seed: int = 7) -> list[parse.Record]:
    """Synthetic but structurally faithful data so the site runs with no creds.

    Shapes that matter are preserved: a long right tail, premium processing
    far faster, category-dependent medians, worsening backlog over time, and —
    critically — recent cohorts dominated by censored (still-waiting) rows.
    """
    rng = random.Random(seed)
    today = datetime.now(timezone.utc).date()
    out: list[parse.Record] = []

    profile = {
        "c03b_opt":     (78, 0.42),
        "c03b_stem":    (85, 0.45),
        "c08_asylum":   (215, 0.55),
        "c09_aos":      (170, 0.50),
        "c26_h4":       (140, 0.48),
        "a17_a18_l2e2": (95, 0.44),
        "other":        (120, 0.50),
    }
    weights = [0.34, 0.14, 0.16, 0.15, 0.10, 0.06, 0.05]
    cats = list(profile)
    centers = list(config.SERVICE_CENTERS)

    for i in range(n):
        cat = rng.choices(cats, weights=weights)[0]
        median, sigma = profile[cat]

        receipt = today - timedelta(days=rng.randint(1, 730))
        # Backlog drift: filings closer to today run slower.
        drift = 1.0 + 0.30 * (1 - (today - receipt).days / 730)
        premium = rng.random() < (0.22 if cat.startswith("c03") else 0.03)

        true_days = max(3, int(rng.lognormvariate(0, sigma) * median * drift))
        if premium:
            true_days = max(5, int(true_days * 0.28))

        elapsed = (today - receipt).days
        if true_days <= elapsed:
            approved = receipt + timedelta(days=true_days)
            posted = min(today, approved + timedelta(days=rng.randint(0, 5)))
            rec = parse.Record(
                source="demo", id=f"demo{i}", permalink="", posted=posted.isoformat(),
                category=cat, center=rng.choice(centers),
                premium=premium, receipt=receipt.isoformat(),
                approved=approved.isoformat(), card_produced=None,
                days=true_days, censored_days=None, event=True)
        else:
            rec = parse.Record(
                source="demo", id=f"demo{i}", permalink="", posted=today.isoformat(),
                category=cat, center=rng.choice(centers),
                premium=premium, receipt=receipt.isoformat(),
                approved=None, card_produced=None,
                days=None, censored_days=elapsed, event=False)
        out.append(rec)

    return out


# ---------------------------------------------------------------------------
# Emit
# ---------------------------------------------------------------------------

def dedupe(records: list[parse.Record]) -> list[parse.Record]:
    """One row per comment id; then drop repeats of the same person's timeline.

    People re-post their line each time a step completes, so the same
    (receipt, category, center) recurs. Keep the most informative version:
    an approval beats a still-waiting row, and a longer wait beats a shorter one.
    """
    by_id: dict[str, parse.Record] = {}
    for r in records:
        by_id.setdefault(r.id, r)

    best: dict[tuple, parse.Record] = {}
    for r in by_id.values():
        key = (r.receipt, r.category, r.center, r.premium)
        cur = best.get(key)
        if cur is None:
            best[key] = r
            continue
        # Prefer an observed approval; otherwise the longer observation.
        if r.event and not cur.event:
            best[key] = r
        elif r.event == cur.event:
            a = r.days if r.event else r.censored_days
            b = cur.days if cur.event else cur.censored_days
            if (a or 0) > (b or 0):
                best[key] = r

    return list(best.values())


def compact(r: parse.Record) -> dict:
    """Small keys — the dataset ships over the wire on every page load."""
    return {
        "r": r.receipt,
        "d": r.days if r.event else r.censored_days,
        "e": 1 if r.event else 0,
        "c": r.category,
        "s": r.center or "",
        "p": (1 if r.premium else 0) if r.premium is not None else -1,
    }


def write_official(bulk: dict | None, history: dict) -> None:
    """The site's primary data file. Official sources only — no Reddit."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    path = os.path.join(config.DATA_DIR, "official.json")

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "period": (bulk or {}).get("period"),
        "buckets": (bulk or {}).get("buckets", []),
        "source_urls": (bulk or {}).get("source_urls", {}),
        # Users think in terms of their own EAD category, not USCIS's coarse
        # buckets. Each category carries both mappings because the quarterly
        # report and the historical factsheet slice the form differently.
        "categories": [{
            "id": c["id"],
            "label": c["label"],
            "history_bucket": uscis_bulk.HISTORY_MAP.get(
                c["id"], uscis_bulk.HISTORY_DEFAULT),
            "premium_eligible": c["id"] in uscis_premium.ELIGIBLE_CATEGORIES,
        } for c in config.CATEGORIES],
        "backlog_detail": (bulk or {}).get("backlog_detail", []),
        "premium": uscis_premium.payload(),
        "history": history,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)

    if bulk:
        print(f"official USCIS data ({bulk['period']}):")
        for b in bulk["buckets"]:
            past = b.get("share_past_target")
            print(f"  {b['bucket']:22} published={b['published_months']}mo  "
                  f"backlog-implied={b['implied_months']}mo  "
                  f"pending={b['pending']:>9,}"
                  + (f"  past-target={past:.0%}" if past is not None else ""))
    else:
        print("! official quarterly data unavailable — site will show history only")

    if (msg := history.get("source_check")):
        print(f"  ! {msg}")
    print(f"wrote {config.DATA_DIR}/official.json")


def write_crowd(records: list[parse.Record], demo: bool) -> None:
    """Optional crowd-sourced layer. Only written when records exist.

    Publishing this is what Reddit's Responsible Builder Policy constrains —
    see the README. The default build never produces it.
    """
    os.makedirs(config.DATA_DIR, exist_ok=True)

    rows = sorted((compact(r) for r in records), key=lambda x: x["r"])
    obs = [(r.days if r.event else r.censored_days, r.event) for r in records]
    obs = [(d, e) for d, e in obs if d is not None]

    dataset = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "demo": demo,
        "n": len(rows),
        "categories": [{"id": c["id"], "label": c["label"]} for c in config.CATEGORIES],
        "centers": sorted(config.SERVICE_CENTERS),
        "records": rows,
    }
    with open(os.path.join(config.DATA_DIR, "dataset.json"), "w", encoding="utf-8") as fh:
        json.dump(dataset, fh, separators=(",", ":"))

    overall = survival.summarize(obs)
    overall.pop("curve", None)
    meta = {
        "generated": dataset["generated"],
        "demo": demo,
        "n": len(rows),
        "n_approved": sum(r["e"] for r in rows),
        "overall": overall,
        "trend": survival.cohort_trend([
            {"receipt": r.receipt,
             "days": r.days, "censored_days": r.censored_days, "event": r.event}
            for r in records]),
    }
    with open(os.path.join(config.DATA_DIR, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)

    print(f"\nwrote {len(rows)} records -> {config.DATA_DIR}/dataset.json")
    print(f"  approvals {meta['n_approved']}  still-waiting {len(rows) - meta['n_approved']}")
    km, naive = overall["km"], overall["naive"]
    print(f"  KM    p50={km['p50']} p80={km['p80']} p90={km['p90']} days")
    print(f"  naive p50={naive['p50']} p80={naive['p80']} p90={naive['p90']} days"
          "   <- biased low; censoring ignored")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Build the EAD-ETA dataset from official USCIS sources.",
        epilog="The default build uses official USCIS data only and needs no "
               "credentials. --reddit adds a crowd-sourced layer; read the "
               "README on Reddit's Responsible Builder Policy before using it.")
    ap.add_argument("--reddit", action="store_true",
                    help="also collect crowd timelines from Reddit (opt-in; see README)")
    ap.add_argument("--demo", action="store_true",
                    help="synthetic crowd layer for UI development, no network")
    ap.add_argument("--pullpush", action="store_true",
                    help="with --reddit, also try the historical archive (best effort)")
    ap.add_argument("--no-official", action="store_true",
                    help="skip the official USCIS fetch (offline UI work)")
    ap.add_argument("--max-threads", type=int, metavar="N",
                    help="with --reddit, crawl only the N busiest threads")
    ap.add_argument("--save-raw", action="store_true",
                    help=f"with --reddit, dump raw comments to {config.RAW_DIR}/")
    args = ap.parse_args(argv)

    # ---- official layer (default, no credentials) ----
    if not args.no_official:
        print("fetching official USCIS data ...")
        bulk = uscis_bulk.fetch()
        history = uscis_history.payload(verify=True)
        write_official(bulk, history)

    # ---- optional crowd layer ----
    records: list[parse.Record] = []
    demo = args.demo

    if args.demo:
        print("\nbuilding synthetic crowd layer (--demo)")
        records = make_demo()
    elif args.reddit:
        print("\ncollecting crowd timelines from Reddit ...")
        print("  reminder: publishing this layer is constrained by Reddit's")
        print("  Responsible Builder Policy — see the README before deploying.")
        if reddit_api.available():
            records += collect_reddit_api(args.max_threads, args.save_raw)
        else:
            print("! REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set")
            return 1
        if args.pullpush:
            records += collect_pullpush()

    if records:
        before = len(records)
        records = dedupe(records)
        print(f"\n{before} parsed -> {len(records)} after dedupe")
        write_crowd(records, demo)
    else:
        print("\nno crowd layer (official data only) — this is the default")

    return 0


if __name__ == "__main__":
    sys.exit(main())
