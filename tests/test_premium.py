"""Premium processing facts and the two-report bucket asymmetry. No network."""

from __future__ import annotations

import pytest

from scraper import config
from scraper.sources import uscis_bulk as ub
from scraper.sources import uscis_premium as up


def test_only_f1_opt_categories_are_premium_eligible():
    """USCIS allows premium on I-765 for (c)(3)(A), (B) and (C) only."""
    assert set(up.ELIGIBLE_CATEGORIES) == {"c03a_preopt", "c03b_opt", "c03b_stem"}
    for cid in up.ELIGIBLE_CATEGORIES:
        assert cid in config.CATEGORY_IDS, f"{cid} is not a known category"


def test_guarantee_is_business_days_not_calendar():
    """The 30 is business days — conflating the two understates it by ~40%."""
    p = up.payload()
    assert p["business_days"] == 30
    assert p["approx_calendar_days"] > p["business_days"]
    assert any("business" in c.lower() for c in p["caveats"])


def test_guarantee_covers_action_not_approval():
    """An RFE satisfies the guarantee; the UI must not promise an approval."""
    p = up.payload()
    assert "adjudicative action" in p["guarantee"]
    assert any("RFE" in c for c in p["caveats"])


def test_no_fee_amount_is_asserted():
    """The fee changed in 2026 and isn't machine-readable; we link instead."""
    blob = repr(up.payload())
    assert "$" not in blob
    assert up.payload()["links"]["fee_schedule"].startswith("https://www.uscis.gov")


def test_history_map_covers_every_category():
    """Every category resolves to a history series or an explicit None."""
    for cid in config.CATEGORY_IDS:
        key = ub.HISTORY_MAP.get(cid, ub.HISTORY_DEFAULT)
        assert key is None or isinstance(key, str)


def test_parole_maps_to_its_own_history_series():
    """Regression: parole used to highlight the catch-all trend line.

    The factsheet breaks parole out; the quarterly report does not. Selecting
    parole must bold the parole line, not "All other".
    """
    assert ub.HISTORY_MAP["c11_parole"] == "parolees"
    assert "c11_parole" in ub.BUCKET_MAP["all other"]


def test_daca_has_no_history_series():
    """The factsheet has no DACA row; pretending otherwise would invent data."""
    assert ub.HISTORY_MAP["c33_daca"] is None


def test_bucket_map_still_an_exact_cover():
    mapped = [c for cats in ub.BUCKET_MAP.values() for c in cats]
    assert len(mapped) == len(set(mapped)), "a category appears in two buckets"
    assert set(mapped) == set(config.CATEGORY_IDS)


@pytest.mark.parametrize("key", ["premium processed", "parolees"])
def test_backlog_only_buckets_are_not_in_the_quarterly_map(key):
    """These two exist only in the backlog report and were silently dropped.

    They must not be quarterly buckets (they have no pending or published time),
    but they must still reach the front end via backlog_detail.
    """
    assert key not in ub.BUCKET_MAP
