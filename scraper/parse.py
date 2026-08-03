"""Turn a free-text Reddit comment into a structured EAD timeline record.

The r/USCIS megathreads use a loose numbered template::

    1. Application type: Post-OPT
    2. Premium Processing: Yes
    3. Receipt Date: 05/01/2025
    4. Approved Date: 05/19/2025
    5. Card Produced Date:

...but roughly half of real posts drift from it ("filed 1/15, approved 4/2"),
so every field is matched by label *aliases* scanned line-by-line, and the
template is treated as a happy path rather than a requirement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone

from . import config

# ---------------------------------------------------------------------------
# Date extraction
# ---------------------------------------------------------------------------

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

# 05/01/2025 · 5-1-25 · 05.01.2025
_NUMERIC = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\b")
# 2025-05-01
_ISO = re.compile(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b")
# May 1, 2025 · 1 May 2025 · May 1st
_ALPHA_MD = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?(?:[,\s]+(\d{2,4}))?\b", re.I)
_ALPHA_DM = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
    r"(?:[,\s]+(\d{2,4}))?\b", re.I)


def _norm_year(y: int | None, fallback: int) -> int:
    """Two-digit years and missing years both resolve against the post date."""
    if y is None:
        return fallback
    if y < 100:
        return 2000 + y
    return y


def _mk(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def find_date(text: str, context_year: int) -> date | None:
    """First plausible date in `text`. US month/day ordering."""
    if not text:
        return None

    if (m := _ISO.search(text)):
        return _mk(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    if (m := _ALPHA_MD.search(text)):
        mon = _MONTHS[m.group(1).lower()[:4].rstrip(".")] if m.group(1).lower()[:4] in _MONTHS \
            else _MONTHS[m.group(1).lower()[:3]]
        return _mk(_norm_year(int(m.group(3)) if m.group(3) else None, context_year),
                   mon, int(m.group(2)))

    if (m := _ALPHA_DM.search(text)):
        key = m.group(2).lower()
        mon = _MONTHS.get(key[:4]) or _MONTHS[key[:3]]
        return _mk(_norm_year(int(m.group(3)) if m.group(3) else None, context_year),
                   mon, int(m.group(1)))

    if (m := _NUMERIC.search(text)):
        a, b = int(m.group(1)), int(m.group(2))
        year = _norm_year(int(m.group(3)) if m.group(3) else None, context_year)
        if a > 12 and b <= 12:       # 25/05 -> day/month, someone typed it backwards
            a, b = b, a
        return _mk(year, a, b)

    return None


# ---------------------------------------------------------------------------
# Field labels
# ---------------------------------------------------------------------------

_FIELDS: dict[str, list[str]] = {
    "receipt": [
        "receipt date", "received date", "receipt notice date", "receipt",
        "filing date", "filed on", "filed date", "date filed", "applied on",
        "application date", "date of filing", "submitted on", "filed", "applied",
    ],
    "biometrics": ["biometrics", "biometric", "fingerprint", "asc appointment"],
    "approved": [
        "approved date", "approval date", "date approved", "case approved",
        "ead approved", "approved on", "approval", "approved",
    ],
    "card_produced": ["card produced date", "card was produced", "card produced", "card is being produced"],
    "card_mailed": ["card shipped", "card mailed", "card was mailed", "card sent"],
    "card_delivered": ["card delivered", "card in hand", "card received", "received card"],
}

# Lines that mention a date but are commentary, not a report.
_NOISE = re.compile(
    r"\b(my friend|someone i know|i heard|last year i|previous(ly)? applied|"
    r"expires? on|expiration|valid (until|through)|interview|"
    r"my (h1b|h-1b|opt) (start|end)s?)\b", re.I)


def _label_hit(line: str, aliases: list[str]) -> int | None:
    """Index just past the matched label, or None."""
    low = line.lower()
    for alias in aliases:
        # Label must be followed by a separator so "approved" doesn't fire on
        # "approved for" in prose, and so "filed" needs a colon or a date after.
        for pat in (rf"\b{re.escape(alias)}\s*[:\-–=]\s*", rf"\b{re.escape(alias)}\s+(?=\d|\w+\s+\d)"):
            if (m := re.search(pat, low)):
                return m.end()
    return None


# Prose fallbacks: "I applied for my STEM OPT on March 19, 2025", "filed back in
# Jan". The verb may sit well before the date, so allow a short gap — but keep it
# bounded so a verb can't reach across a sentence and grab an unrelated date.
_GAP = r"[^.\n!?;]{0,45}?"
_LOOSE = {
    "receipt": re.compile(
        rf"\b(?:i\s+)?(?:applied|filed|submitted|sent|mailed)\b(?:\s+(?:for|my|it|in|out))*{_GAP}"
        rf"\b(?:on|in|back in|around)?\s*(?=[\d(]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", re.I),
    "approved": re.compile(
        rf"\b(?:got|was|been|is)\s+approved\b{_GAP}"
        rf"\b(?:on|in)?\s*(?=[\d(]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", re.I),
}


def extract_fields(body: str, context_year: int) -> dict[str, date]:
    """Scan line by line; a label claims only the dates on its own line.

    Two passes: the numbered-template labels first, then looser prose patterns
    for anything still unfilled. Strict wins so a well-formed post is never
    reinterpreted by the fuzzy rules.
    """
    out: dict[str, date] = {}
    lines = [ln.strip() for ln in
             re.split(r"[\n\r]+|(?<=\d{4})\s*(?=\d+\.\s)", body)]

    for line in lines:
        if not line or _NOISE.search(line):
            continue
        # Longest aliases first so "approval date" beats "approved".
        for field, aliases in _FIELDS.items():
            if field in out:
                continue
            idx = _label_hit(line, sorted(aliases, key=len, reverse=True))
            if idx is None:
                continue
            if (d := find_date(line[idx:], context_year)):
                out[field] = d

    for field, pat in _LOOSE.items():
        if field in out:
            continue
        for line in lines:
            if not line or _NOISE.search(line):
                continue
            if (m := pat.search(line)) and (d := find_date(line[m.end():], context_year)):
                out[field] = d
                break

    return out


# ---------------------------------------------------------------------------
# Categorical fields
# ---------------------------------------------------------------------------

_RECEIPT_NUM = re.compile(r"\b(IOE|LIN|SRC|WAC|EAC|YSC|MSC|NBC)\s*[-]?\s*(\d{9,10})\b", re.I)


def detect_category(text: str) -> str:
    low = text.lower()
    for cat in config.CATEGORIES:
        for key in cat["keys"]:
            if key in low:
                return cat["id"]
    return "other"


def detect_center(text: str) -> str | None:
    if (m := _RECEIPT_NUM.search(text)):
        return config.RECEIPT_PREFIX_CENTER.get(m.group(1).upper())
    low = text.lower()
    for center, keys in config.SERVICE_CENTERS.items():
        if any(k in low for k in keys):
            return center
    return None


def detect_premium(text: str) -> bool | None:
    """Premium processing changes the distribution enormously — keep it separate."""
    low = text.lower()
    if not re.search(r"premium|i-?907|\bpp\b", low):
        return None
    m = re.search(r"(premium\s*(processing)?|i-?907|\bpp\b)\s*[:\-–]?\s*(yes|no|y|n|true|false|none|n/a)\b", low)
    if m:
        return m.group(3) in ("yes", "y", "true")
    if re.search(r"\b(no|not|didn'?t|did not|without)\s+(use\s+)?(premium|pp)\b", low):
        return False
    if re.search(r"(upgraded to|applied|filed|with|used)\s+(premium|pp)|premium\s+(applied|filed)", low):
        return True
    return None


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------

@dataclass
class Record:
    source: str
    id: str
    permalink: str
    posted: str              # ISO date the comment was written
    category: str
    center: str | None
    premium: bool | None
    receipt: str
    approved: str | None
    card_produced: str | None
    days: int | None         # receipt -> approved, when approved
    censored_days: int | None  # receipt -> post date, when still waiting
    event: bool              # True = approval observed, False = right-censored

    def as_dict(self) -> dict:
        return asdict(self)


def parse_comment(body: str, created_utc: float, cid: str, permalink: str,
                  source: str = "reddit", thread_title: str = "") -> Record | None:
    """Return a Record, or None if the text isn't a usable timeline report.

    Comments that give a receipt date but no approval become *right-censored*
    observations rather than being discarded — dropping them is exactly the
    survivorship bias that makes naive EAD estimates too optimistic.
    """
    if not body or len(body) < config.MIN_BODY_LEN or body in ("[deleted]", "[removed]"):
        return None

    posted = datetime.fromtimestamp(created_utc, timezone.utc).date()
    fields = extract_fields(body, posted.year)

    receipt = fields.get("receipt")
    if not receipt:
        return None

    approved = fields.get("approved")
    # A date in the future, or before EAD tracking was meaningful, is a typo.
    if receipt > posted or receipt.year < 2015:
        return None

    haystack = f"{thread_title}\n{body}"

    if approved:
        if approved < receipt or approved > posted:
            return None
        days = (approved - receipt).days
        if days > config.MAX_REASONABLE_DAYS:
            return None
        censored_days, event = None, True
    else:
        days = None
        censored_days = (posted - receipt).days
        if censored_days > config.MAX_REASONABLE_DAYS:
            return None
        event = False

    return Record(
        source=source,
        id=cid,
        permalink=permalink,
        posted=posted.isoformat(),
        category=detect_category(haystack),
        center=detect_center(haystack),
        premium=detect_premium(haystack),
        receipt=receipt.isoformat(),
        approved=approved.isoformat() if approved else None,
        card_produced=(fields["card_produced"].isoformat()
                       if fields.get("card_produced") else None),
        days=days,
        censored_days=censored_days,
        event=event,
    )
