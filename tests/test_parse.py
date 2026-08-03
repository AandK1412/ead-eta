"""Parser and estimator tests. No network — run with `python -m pytest tests/`."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from scraper import parse, survival


def ts(iso: str) -> float:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp()


def rec(body: str, posted: str = "2025-06-01"):
    return parse.parse_comment(body, ts(posted), "cid", "/r/USCIS/x/", "test")


# --------------------------------------------------------------- dates

@pytest.mark.parametrize("text,expected", [
    ("05/01/2025", (2025, 5, 1)),
    ("5-1-25", (2025, 5, 1)),
    ("2025-05-01", (2025, 5, 1)),
    ("May 1, 2025", (2025, 5, 1)),
    ("1 May 2025", (2025, 5, 1)),
    ("March 19th, 2025", (2025, 3, 19)),
    ("Jan 3", (2026, 1, 3)),          # year falls back to context
])
def test_find_date(text, expected):
    assert parse.find_date(text, 2026) == __import__("datetime").date(*expected)


def test_rejects_impossible_date():
    assert parse.find_date("02/30/2025", 2025) is None


# --------------------------------------------------------------- template

def test_numbered_template():
    r = rec("""1. Application type: Post-OPT
2. Premium Processing: Yes (Applied on the same date)
3. Receipt Date: 05/01/2025
4. Approved Date: 05/19/2025 (Through email by 8:19 AM)
5. Card Produced Date:
6. Card shipped:""")
    assert r is not None
    assert r.receipt == "2025-05-01"
    assert r.approved == "2025-05-19"
    assert r.days == 18
    assert r.event is True
    assert r.premium is True
    assert r.category == "c03b_opt"


def test_template_on_one_line():
    r = rec("1. Application type: STEM OPT 2. Premium: No 3. Receipt Date: 03/21/2025 "
            "4. Approved Date: 05/10/2025")
    assert r is not None and r.days == 50 and r.category == "c03b_stem"


# --------------------------------------------------------------- censoring

def test_still_waiting_is_censored_not_dropped():
    r = rec("Receipt date: 03/28/2025, still waiting, no updates", posted="2025-05-19")
    assert r is not None
    assert r.event is False
    assert r.approved is None
    assert r.censored_days == 52


def test_prose_fallback_creates_censored_record():
    r = rec("I applied for my stem opt on March 19, 2025 and my case still shows 3 months",
            posted="2025-05-19")
    assert r is not None
    assert r.event is False
    assert r.receipt == "2025-03-19"


def test_prose_approval():
    r = rec("Filed 01/15/2025 and finally got approved on 04/02/2025!", posted="2025-04-03")
    assert r is not None and r.event is True and r.days == 77


# --------------------------------------------------------------- rejection

@pytest.mark.parametrize("body", [
    "F",
    "Hopefully we'll get it this week.",
    "Anyone with 3/14 date still not approved??",   # a question, no self-report
    "[deleted]",
])
def test_non_reports_rejected(body):
    assert rec(body) is None


def test_approval_before_receipt_rejected():
    assert rec("Receipt Date: 05/01/2025\nApproved Date: 01/01/2025") is None


def test_future_receipt_rejected():
    assert rec("Receipt Date: 12/01/2025", posted="2025-06-01") is None


def test_expiry_line_is_not_a_receipt_date():
    assert rec("My current EAD expires on 05/01/2025, worried about the gap") is None


# --------------------------------------------------------------- categorical

@pytest.mark.parametrize("text,cat", [
    ("my c8 EAD renewal", "c08_asylum"),
    ("H4 EAD filed with I-539", "c26_h4"),
    ("stem opt extension", "c03b_stem"),
    ("(c)(9) combo card", "c09_aos"),
    ("random text", "other"),
])
def test_detect_category(text, cat):
    assert parse.detect_category(text) == cat


def test_center_from_receipt_number():
    assert parse.detect_center("my number is IOE0912345678") == "nbc"
    assert parse.detect_center("LIN2390123456") == "nebraska"


def test_premium_detection():
    assert parse.detect_premium("Premium Processing: Yes") is True
    assert parse.detect_premium("premium: no") is False
    assert parse.detect_premium("nothing relevant here") is None


# --------------------------------------------------------------- survival

def test_km_no_censoring_matches_empirical():
    obs = [(10, True), (20, True), (30, True), (40, True)]
    curve = survival.kaplan_meier(obs)
    assert survival.percentile(curve, 0.50) == 20
    assert curve[-1]["survival"] == pytest.approx(0.0, abs=1e-9)


def test_censoring_pushes_estimate_later():
    """Censored rows must make the estimate slower, never faster."""
    approved_only = [(10, True), (20, True), (30, True)]
    with_waiters = approved_only + [(100, False)] * 20

    p_naive = survival.percentile(survival.kaplan_meier(approved_only), 0.50)
    p_censored = survival.percentile(survival.kaplan_meier(with_waiters), 0.50)
    assert p_censored is None or p_censored >= p_naive


def test_percentile_returns_none_beyond_data():
    obs = [(10, True), (50, False), (60, False)]
    assert survival.percentile(survival.kaplan_meier(obs), 0.90) is None


def test_conditional_curve_rebases_to_one():
    obs = [(t, True) for t in range(10, 210, 10)]
    curve = survival.kaplan_meier(obs)
    cond = survival.conditional_curve(curve, 100)
    assert cond[0]["survival"] == pytest.approx(1.0, abs=1e-6)
    assert all(r["t"] >= 100 for r in cond)


def test_conditional_median_exceeds_unconditional():
    obs = [(t, True) for t in range(10, 410, 10)]
    curve = survival.kaplan_meier(obs)
    uncond = survival.percentile(curve, 0.5)
    cond = survival.percentile(survival.conditional_curve(curve, 200), 0.5)
    assert cond > uncond


def test_naive_is_optimistic_vs_km():
    """The headline claim of the project, asserted."""
    obs = [(d, True) for d in (30, 45, 60, 75, 90)] + [(120, False)] * 15
    km = survival.percentile(survival.kaplan_meier(obs), 0.80)
    naive = survival.naive_percentiles([d for d, e in obs if e])["p80"]
    assert km is None or km > naive


def test_empty_inputs():
    assert survival.kaplan_meier([]) == []
    assert survival.percentile([], 0.5) is None
    assert survival.cohort_trend([]) == []
