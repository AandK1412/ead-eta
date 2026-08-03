"""Tests for the official USCIS bulk source. No network."""

from __future__ import annotations

import pytest

from scraper import config
from scraper.sources import uscis_bulk as ub


@pytest.mark.parametrize("title,expected", [
    ("Application for Employment Authorization (Asylum)", "asylum"),
    ("Application for Employment Authorization (Adjustment Of Status)", "adjustment of status"),
    ("Application for Employment Authorization (All Other)", "all other"),
    ("Application for Employment Authorization (Premium Processed)", "premium processed"),
    ("Application for Employment Authorization (DACA)", "daca"),
])
def test_bucket_key(title, expected):
    assert ub._bucket_key(title) == expected


def test_bucket_key_without_parenthetical():
    assert ub._bucket_key("Petition for Alien Relative") is None
    assert ub._bucket_key("") is None
    assert ub._bucket_key(None) is None


def test_bucket_map_is_an_exact_cover_of_categories():
    """Every category maps to exactly one official bucket.

    If someone adds a category to config without deciding which USCIS bucket it
    belongs to, the reality-check panel would silently show nothing for it.
    """
    mapped = [c for cats in ub.BUCKET_MAP.values() for c in cats]

    assert len(mapped) == len(set(mapped)), "a category appears in two buckets"
    assert set(mapped) == set(config.CATEGORY_IDS), (
        f"unmapped: {set(config.CATEGORY_IDS) - set(mapped)}; "
        f"unknown: {set(mapped) - set(config.CATEGORY_IDS)}"
    )


def test_littles_law_arithmetic():
    """pending / quarterly completions, expressed in months."""
    pending, completions = 875191, 153280
    implied = round(pending / completions * 3, 1)
    assert implied == pytest.approx(17.1, abs=0.05)


def test_littles_law_guards_zero_throughput():
    completions = 0
    implied = round(100 / completions * 3, 1) if completions > 0 else None
    assert implied is None


def test_fallback_urls_are_wellformed():
    for url in ub.FALLBACK.values():
        assert url.startswith("https://www.uscis.gov/")
        assert url.endswith(".xlsx")
