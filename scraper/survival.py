"""Survival analysis for right-censored EAD waiting times.

Why not just average the approval times people post?

Because the data is *right-censored* and self-selected. At any moment, the
people who filed recently and have already been approved are the fast tail —
everyone else is still waiting and has not posted an approval yet. Averaging
only approvals therefore makes recent cohorts look dramatically faster than
they are, and the bias grows the more recent the cohort.

The Kaplan-Meier estimator handles this: a comment that says "filed 01/2025,
still waiting" as of its post date is a censored observation contributing
"survived at least N days" without claiming to know the total. Both the
censored-aware and the naive numbers are computed so the site can show the gap.

Pure stdlib — keeps the GitHub Action dependency-free and the math auditable.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date

Observation = tuple[int, bool]  # (duration_days, event_observed)

Z = 1.959964  # 95%


def kaplan_meier(obs: list[Observation]) -> list[dict]:
    """Return the KM step function with Greenwood 95% bands.

    Each row: {t, survival, lower, upper, at_risk, events}.
    """
    if not obs:
        return []

    events_at: dict[int, int] = defaultdict(int)
    censored_at: dict[int, int] = defaultdict(int)
    for t, ev in obs:
        (events_at if ev else censored_at)[t] += 1

    times = sorted(set(events_at) | set(censored_at))
    n_at_risk = len(obs)

    surv = 1.0
    green_sum = 0.0
    curve = [{"t": 0, "survival": 1.0, "lower": 1.0, "upper": 1.0,
              "at_risk": n_at_risk, "events": 0}]

    for t in times:
        d = events_at.get(t, 0)
        c = censored_at.get(t, 0)
        n = n_at_risk

        if n > 0 and d > 0:
            surv *= (1 - d / n)
            if n - d > 0:
                green_sum += d / (n * (n - d))

        se = surv * math.sqrt(green_sum) if green_sum > 0 else 0.0
        curve.append({
            "t": t,
            "survival": round(surv, 5),
            "lower": round(max(0.0, surv - Z * se), 5),
            "upper": round(min(1.0, surv + Z * se), 5),
            "at_risk": n,
            "events": d,
        })
        n_at_risk -= (d + c)

    return curve


def percentile(curve: list[dict], p: float) -> int | None:
    """Days by which fraction `p` of cases are approved. None if unreached.

    None is meaningful: it says the observed data never gets that far, so the
    honest answer is "beyond our data" rather than an extrapolated guess.
    """
    target = 1.0 - p
    for row in curve:
        if row["survival"] <= target:
            return row["t"]
    return None


def conditional_curve(curve: list[dict], elapsed: int) -> list[dict]:
    """Re-base the curve on 'already waited `elapsed` days and still waiting'.

    This is the number an applicant actually wants. Having survived 200 days
    already, the relevant distribution is P(T > t | T > 200) — surviving the
    early mass is information, and unconditional percentiles understate the
    remaining wait for anyone past the median.
    """
    if not curve:
        return []

    s_at = 1.0
    for row in curve:
        if row["t"] <= elapsed:
            s_at = row["survival"]
        else:
            break

    if s_at <= 0:
        return []

    return [
        {**row,
         "t": row["t"],
         "survival": round(min(1.0, row["survival"] / s_at), 5),
         "lower": round(min(1.0, row["lower"] / s_at), 5),
         "upper": round(min(1.0, row["upper"] / s_at), 5)}
        for row in curve if row["t"] >= elapsed
    ]


def naive_percentiles(durations: list[int]) -> dict[str, int | None]:
    """Approved-only quantiles — the biased number, kept for comparison."""
    if not durations:
        return {"p50": None, "p80": None, "p90": None}
    s = sorted(durations)

    def q(p: float) -> int:
        idx = min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))
        return s[idx]

    return {"p50": q(0.50), "p80": q(0.80), "p90": q(0.90)}


def summarize(obs: list[Observation]) -> dict:
    """Headline stats for one cohort."""
    curve = kaplan_meier(obs)
    approved = [t for t, ev in obs if ev]
    return {
        "n": len(obs),
        "n_approved": len(approved),
        "n_waiting": len(obs) - len(approved),
        "km": {"p50": percentile(curve, 0.50),
               "p80": percentile(curve, 0.80),
               "p90": percentile(curve, 0.90)},
        "naive": naive_percentiles(approved),
        "curve": curve,
    }


def cohort_trend(records: list[dict], min_n: int = 5) -> list[dict]:
    """Median wait by receipt month — the 'is it getting worse?' series.

    Recent months are censored-heavy by construction, so each point carries its
    completion rate; the front end fades points below `min_n` and flags months
    where too few cases have resolved for the median to be trustworthy.
    """
    buckets: dict[str, list[Observation]] = defaultdict(list)
    for r in records:
        month = r["receipt"][:7]
        dur = r["days"] if r["event"] else r["censored_days"]
        if dur is None:
            continue
        buckets[month].append((dur, r["event"]))

    out = []
    for month in sorted(buckets):
        obs = buckets[month]
        if len(obs) < min_n:
            continue
        curve = kaplan_meier(obs)
        n_ev = sum(1 for _, ev in obs if ev)
        out.append({
            "month": month,
            "n": len(obs),
            "n_approved": n_ev,
            "completion_rate": round(n_ev / len(obs), 3),
            "p50": percentile(curve, 0.50),
            "p80": percentile(curve, 0.80),
            "naive_p50": naive_percentiles([t for t, ev in obs if ev])["p50"],
        })
    return out


def histogram(durations: list[int], bin_days: int = 15) -> list[dict]:
    """Binned approval times for the distribution chart."""
    if not durations:
        return []
    hi = max(durations)
    counts: dict[int, int] = defaultdict(int)
    for d in durations:
        counts[(d // bin_days) * bin_days] += 1
    return [{"bin": b, "count": counts.get(b, 0)}
            for b in range(0, hi + bin_days, bin_days)]
