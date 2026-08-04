"""Shared configuration: EAD categories, source threads, and tunables."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# EAD / I-765 eligibility categories
#
# `keys` are lowercase substrings matched against the free text of a post. Order
# matters: the first category whose key appears wins, so put the specific ones
# (stem opt) ahead of the general ones (opt).
# ---------------------------------------------------------------------------

CATEGORIES = [
    {
        "id": "c03b_stem",
        "label": "STEM OPT extension — (c)(3)(C)",
        "keys": ["stem opt", "stem-opt", "c3c", "c(3)(c)", "(c)(3)(c)", "24 month ext"],
    },
    {
        "id": "c03a_preopt",
        "label": "Pre-completion OPT — (c)(3)(A)",
        "keys": ["pre-opt", "pre opt", "precompletion", "pre-completion", "c3a", "(c)(3)(a)"],
    },
    {
        "id": "c03b_opt",
        "label": "Post-completion OPT — (c)(3)(B)",
        "keys": ["post-opt", "post opt", "postcompletion", "post-completion",
                 "initial opt", "c3b", "(c)(3)(b)", "opt"],
    },
    {
        "id": "c08_asylum",
        "label": "Asylum pending — (c)(8)",
        "keys": ["c8", "c(8)", "(c)(8)", "asylum pending", "pending asylum", "asylum based ead"],
    },
    {
        # Kept short enough to fit the sidebar select without truncating.
        "id": "c09_aos",
        "label": "Adjustment of status — (c)(9)",
        "keys": ["c9", "c(9)", "(c)(9)", "i-485 based", "aos based", "combo card", "adjustment of status"],
    },
    {
        "id": "c26_h4",
        "label": "H-4 spouse — (c)(26)",
        "keys": ["c26", "c(26)", "(c)(26)", "h4 ead", "h-4 ead", "h4ead", "h-4 spouse"],
    },
    {
        "id": "a17_a18_l2e2",
        "label": "L-2 / E-2 spouse — (a)(17)/(a)(18)",
        "keys": ["a17", "a18", "(a)(17)", "(a)(18)", "l2 ead", "l-2 ead", "l2s", "e2 spouse", "e-2 spouse"],
    },
    {
        "id": "a05_asylee",
        "label": "Granted asylum — (a)(5)",
        "keys": ["a5", "(a)(5)", "asylee ead", "granted asylum"],
    },
    {
        "id": "c11_parole",
        "label": "Parole — (c)(11)",
        "keys": ["c11", "(c)(11)", "parole ead", "humanitarian parole"],
    },
    {
        "id": "a12_c19_tps",
        "label": "TPS — (a)(12)/(c)(19)",
        "keys": ["a12", "c19", "(a)(12)", "(c)(19)", "tps ead", "tps based"],
    },
    {
        "id": "c33_daca",
        "label": "DACA — (c)(33)",
        "keys": ["c33", "(c)(33)", "daca"],
    },
    {"id": "other", "label": "Other / unspecified", "keys": []},
]

CATEGORY_IDS = [c["id"] for c in CATEGORIES]

# USCIS service centers / lockboxes people name in posts.
SERVICE_CENTERS = {
    "nbc": ["nbc", "national benefits"],
    "potomac": ["potomac", "ysc", "psc"],
    "nebraska": ["nebraska", "lin", "nsc"],
    "texas": ["texas", "srb", "src", "tsc"],
    "california": ["california", "wac", "csc"],
    "vermont": ["vermont", "eac", "vsc"],
    "arlington": ["arlington", "iois"],
}

# Receipt-number prefix -> service center. Far more reliable than prose.
RECEIPT_PREFIX_CENTER = {
    "IOE": "nbc",
    "LIN": "nebraska",
    "SRC": "texas",
    "WAC": "california",
    "EAC": "vermont",
    "YSC": "potomac",
    "MSC": "nbc",
    "NBC": "nbc",
}

# ---------------------------------------------------------------------------
# Reddit sources
# ---------------------------------------------------------------------------

SUBREDDITS = ["USCIS", "immigration", "f1visa", "AsylumSeekersUSA", "h1b"]

# Queries used to *discover* megathreads, so the crawler keeps working when the
# mods roll a new thread. Discovered threads are crawled comment-by-comment.
MEGATHREAD_QUERIES = [
    "OPT processing timeline",
    "EAD timeline megathread",
    "I-765 timeline",
    "EAD approval megathread",
    "OPT timeline 2025",
    "OPT timeline 2026",
    "EAD tracker",
    "c08 EAD timeline",
    "H4 EAD timeline",
]

# Threads worth crawling even if search misses them. Bare submission ids.
SEED_THREAD_IDS = [
    "1i6230k",  # 2025 OPT processing timeline
]

# A comment must look like a timeline report to be kept.
MIN_BODY_LEN = 20
MAX_REASONABLE_DAYS = 1500  # anything longer is almost certainly a typo'd year

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

DATA_DIR = "docs/data"
RAW_DIR = "data/raw"
