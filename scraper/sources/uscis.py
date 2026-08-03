"""egov.uscis.gov processing-times API — **currently unreachable; unused.**

Kept for reference and in case the protection changes. Verified 2026-08-02:

    plain requests / curl        -> 403 (Cloudflare)
    curl_cffi impersonate chrome -> 403 (Cloudflare)
    headless browser navigation  -> "Just a moment..." interstitial

The gate is a Cloudflare **JS challenge**, not a TLS-fingerprint check, so
impersonating a Chrome handshake does not help — an earlier version of this file
claimed it did, which was wrong. Clearing it would need a real JS-executing
browser session, which is more fragility than an optional baseline is worth.

The data this would have supplied (a range whose upper bound is roughly a P80)
is genuinely useful and has no substitute in the bulk reports. If USCIS ever
drops the challenge, wiring this back in is the single best way to add
distribution information to the site.

The default build does not call this module. `sources/uscis_bulk.py` and
`sources/uscis_history.py` use www.uscis.gov, which is not behind Cloudflare.
"""

from __future__ import annotations

API = "https://egov.uscis.gov/processing-times/api"
REFERER = "https://egov.uscis.gov/processing-times/"

# I-765 form-office codes as used by the egov API.
OFFICES = ["NBC", "YSC", "LIN", "SRC", "WAC", "EAC"]


def _session():
    try:
        from curl_cffi import requests as cffi
        return cffi.Session(impersonate="chrome124")
    except ImportError:
        return None


def _headers() -> dict:
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": REFERER,
        "Origin": "https://egov.uscis.gov",
    }


def fetch_processing_times(form: str = "I-765") -> dict | None:
    """Return {office: raw payload}. None if Cloudflare can't be cleared.

    USCIS publishes the range in which 80% of cases completed, so the upper
    bound is roughly a P80 — not a median. The site labels it accordingly.
    """
    sess = _session()
    if sess is None:
        print("  ! curl_cffi not installed; skipping official USCIS baseline")
        return None

    out: dict[str, dict] = {}
    for office in OFFICES:
        try:
            r = sess.get(f"{API}/processingtime/{form}/{office}",
                         headers=_headers(), timeout=45)
            if r.status_code == 200:
                out[office] = r.json()
            else:
                print(f"  ! USCIS {form}/{office}: HTTP {r.status_code}")
        except Exception as exc:
            print(f"  ! USCIS {form}/{office}: {exc}")

    return out or None


def summarize(payload: dict | None) -> list[dict]:
    """Flatten the API's nested shape into rows the front end can render."""
    if not payload:
        return []

    rows = []
    for office, blob in payload.items():
        data = (blob or {}).get("data", {}).get("processing_time", {})
        subtypes = data.get("subtypes") or []
        for st in subtypes:
            rng = st.get("range") or []
            lo = next((x for x in rng if x.get("unit") and "1" in str(x.get("value", ""))), None)
            rows.append({
                "office": office,
                "subtype": st.get("form_type") or st.get("subtype_info_en") or "",
                "range": [{"value": x.get("value"), "unit": x.get("unit")} for x in rng],
                "updated": data.get("subtypes_completion_time") or blob.get("updated"),
            })
    return rows
