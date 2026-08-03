"""Historical USCIS median processing times for Form I-765, FY2016-FY2024.

Source: USCIS, "Historical Processing Times Trends, Fiscal Year 2016 - 2024"
<https://www.uscis.gov/sites/default/files/document/fact-sheets/historical_pt_factsheet_fy16_to_fy24.pdf>
(data as of 2024-03-05).

The table is transcribed rather than scraped: it lives in a PDF whose layout
changes between releases, and it is a *fixed historical record* that USCIS
republishes roughly annually. Scraping it weekly would be fragile for no benefit.

There is a second USCIS page covering FY16-FY20 (linked as ARCHIVE below) that
looks like it could cross-check this table. **It cannot**, and the trap is worth
recording: that page publishes *national averages* under a different category
breakdown (it splits out DACA and has no asylum or parole rows), while the
factsheet publishes *medians*. The two disagree on every overlapping year by
construction — for "all other applications", averages run 2.6/3.1/4.2/4.5/4.4
against medians of 2.2/2.5/2.9/3.3/2.4. Treating one as a check on the other
produces false alarms, so this module does not.

Three caveats USCIS states directly, all carried into the UI:

* **FY2024 is partial** — 2023-10-01 to 2024-01-31 only, not a full fiscal year.
* **Not comparable to the current processing-times page.** USCIS calculates
  these with a different methodology (cycle time vs processing time), so the
  historical series shows the *shape* of the trend, not values you can subtract
  from today's published figure.
* These are national figures across all offices, not per-service-center.
"""

from __future__ import annotations

import re

import requests

FACTSHEET = ("https://www.uscis.gov/sites/default/files/document/fact-sheets/"
             "historical_pt_factsheet_fy16_to_fy24.pdf")
ARCHIVE = ("https://www.uscis.gov/archive/historical-national-average-processing-"
           "time-in-months-for-all-uscis-offices-for-select-forms-by")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

FISCAL_YEARS = [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]

# Median months from receipt to completion. Keys align with the quarterly
# report's buckets in uscis_bulk.BUCKET_MAP so the two series can be paired.
SERIES = {
    "asylum": {
        "label": "Based on a pending asylum application",
        "months": [2.0, 1.7, 0.9, 2.0, 2.5, 3.2, 9.2, 1.6, 0.6],
    },
    "adjustment of status": {
        "label": "Based on a pending I-485 adjustment application",
        "months": [2.5, 3.0, 4.1, 5.1, 4.8, 7.1, 6.7, 5.5, 3.6],
    },
    "parolees": {
        "label": "Based on parole",
        "months": [2.6, 2.9, 3.5, 6.1, 4.7, 0.6, 1.1, 1.3, 0.9],
    },
    "all other": {
        "label": "All other applications for employment authorization",
        "months": [2.2, 2.5, 2.9, 3.3, 2.4, 3.0, 4.7, 3.2, 2.9],
    },
}

PARTIAL_YEARS = [2024]

NOTES = [
    "FY2024 covers 2023-10-01 to 2024-01-31 only, not a full fiscal year.",
    "USCIS calculates these historical medians with a different methodology "
    "(cycle time) than the current processing-times page, so the two series "
    "are not directly comparable — read the trend, not the gap.",
    "The federal fiscal year runs 1 October to 30 September.",
]


def check_factsheet_available() -> str | None:
    """Confirm the source PDF is still where we say it is.

    This is provenance, not validation — it cannot check the numbers. If USCIS
    publishes an FY16-FY25 revision at a new URL, this goes stale silently, so
    the returned message is surfaced in the build log.
    """
    try:
        r = requests.head(FACTSHEET, headers={"User-Agent": UA},
                          timeout=30, allow_redirects=True)
        if r.status_code == 200:
            return None
        return f"factsheet URL returned HTTP {r.status_code} — check for a newer release"
    except requests.RequestException as exc:
        return f"could not reach factsheet URL: {exc}"


def payload(verify: bool = False) -> dict:
    series = [
        {
            "bucket": key,
            "label": val["label"],
            "months": val["months"],
            # Percent change across the full window, for a plain-language summary.
            "change_pct": round(
                (val["months"][-1] - val["months"][0]) / val["months"][0] * 100),
        }
        for key, val in SERIES.items()
    ]
    out = {
        "fiscal_years": FISCAL_YEARS,
        "partial_years": PARTIAL_YEARS,
        "series": series,
        "notes": NOTES,
        "source": {"factsheet": FACTSHEET, "archive": ARCHIVE,
                   "as_of": "2024-03-05"},
    }
    if verify:
        out["source_check"] = check_factsheet_available()
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(payload(verify=True), indent=1))
