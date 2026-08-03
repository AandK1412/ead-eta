"""Premium processing (Form I-907) rules for Form I-765.

Facts transcribed from USCIS's own page and verified against it on 2026-08-03:
<https://www.uscis.gov/forms/all-forms/how-do-i-request-premium-processing>

Two details that matter more than the headline and are easy to get wrong:

* The guarantee is **30 business days**, not 30 calendar days — roughly six
  calendar weeks, not one month.
* The guarantee is on **adjudicative action**, not approval. USCIS issuing an
  RFE stops the clock and satisfies the guarantee; a new period starts when you
  respond. Premium buys you a decision *or a question*, quickly — it does not
  buy an approval in 30 days.

The fee is deliberately not asserted here. USCIS's I-907 page defers to its fee
schedule, which isn't machine-readable, and the amount changed in 2026. The UI
links to the fee schedule instead of printing a number that could go stale on a
page people use to make a $1,600-ish decision.
"""

from __future__ import annotations

SOURCE = "https://www.uscis.gov/forms/all-forms/how-do-i-request-premium-processing"
FEE_SCHEDULE = "https://www.uscis.gov/forms/filing-fees"
FORM = "https://www.uscis.gov/i-907"

VERIFIED = "2026-08-03"

# Only these I-765 categories can request premium processing. F-1 students only.
ELIGIBLE_CATEGORIES = ["c03a_preopt", "c03b_opt", "c03b_stem"]

BUSINESS_DAYS = 30


def payload() -> dict:
    return {
        "business_days": BUSINESS_DAYS,
        # ~1.4 calendar days per business day, allowing for weekends and holidays.
        "approx_calendar_days": round(BUSINESS_DAYS * 1.4),
        "eligible_categories": ELIGIBLE_CATEGORIES,
        "eligible_label": "F-1 students only — (c)(3)(A), (c)(3)(B), (c)(3)(C)",
        "guarantee": (
            "USCIS guarantees adjudicative action within 30 business days, or it "
            "refunds the premium processing fee."
        ),
        "caveats": [
            "30 <strong>business</strong> days — about six calendar weeks, not one month.",
            "The guarantee is on <strong>adjudicative action</strong>, not approval. "
            "An RFE counts as action and stops the clock; a fresh 30-day period "
            "starts once you respond.",
            "After approval, USCIS says the card itself should be produced within "
            "about two weeks, then mailed.",
            "You can file Form I-907 with your I-765 or upgrade a case that is "
            "already pending, online or through the Chicago Lockbox.",
        ],
        "links": {"source": SOURCE, "fee_schedule": FEE_SCHEDULE, "form": FORM},
        "verified": VERIFIED,
    }
