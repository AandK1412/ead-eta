# EAD ETA

**How long is the I-765 queue really?**

A static, GitHub Pages–hostable tool that shows where your EAD application sits
in the USCIS queue — built entirely from **official USCIS data**, with no
crowd-sourced guesswork and no API credentials.

Enter your receipt date and category; it returns how your wait compares to the
published processing time, how deep the backlog actually is, and nine years of
official medians for your basis of filing.

---

## The thing that makes this different

USCIS publishes a processing time for Form I-765. **It is a median of cases the
agency finished**, which means it describes completed cases rather than the queue
you are standing in. Anyone still stuck contributes nothing to it.

There is a second number derivable from the same quarterly report, and the two
disagree badly. Dividing the pending backlog by quarterly throughput
([Little's Law](https://en.wikipedia.org/wiki/Little%27s_law)) gives an
independent estimate of how long the queue is:

| I-765 bucket | Pending | Published | Backlog-implied | Past USCIS target |
|---|---|---|---|---|
| Asylum | 124,993 | 0.8 mo | 1.2 mo | 0% |
| Adjustment of status | 461,884 | 4.4 mo | 16.0 mo | 62% |
| DACA | 159,122 | 1.9 mo | 13.1 mo | 0% |
| All other (OPT, H-4, L-2) | 875,191 | 4.1 mo | **17.1 mo** | **78%** |

*FY2026 Q1. "All other" filings arrive at 0.99× the rate they're completed —
near steady state, which is where Little's Law is most trustworthy.*

The site shows both readings side by side and states which regime the queue is
in, because a backlog estimate means something different for a queue that's
growing than for one that's draining.

**What it deliberately does not do:** invent percentiles. USCIS publishes
aggregate counts, not per-case durations, so there is no honest way to derive a
P80 or P90 from them. A tool that shows you one has modelled it, not measured it.

---

## Quick start

```bash
git clone https://github.com/YOU/ead-eta && cd ead-eta
pip install -r requirements.txt
python -m scraper.build            # official USCIS data, no credentials
python -m http.server 8765 --directory docs
```

Open <http://localhost:8765>. That's real USCIS data on first run — there is no
demo mode to opt out of and nothing to configure.

Live at **<https://aandk1412.github.io/ead-eta/>**.

---

## Data sources

### Official USCIS — the default, and all the site ships with

No credentials, no approval, no third-party terms. `python -m scraper.build`
pulls everything and writes `docs/data/official.json`. Three publications:

| Source | Gives | Module |
|---|---|---|
| Quarterly *All USCIS Application and Petition Form Types* (XLSX) | Receipts, completions, pending, published processing time, per I-765 bucket | `sources/uscis_bulk.py` |
| *Net Backlog and Frontlog* (XLSX) | Pending cases past USCIS's own target | `sources/uscis_bulk.py` |
| *Historical Processing Times Trends FY2016–FY2024* (PDF) | Nine years of national medians by basis of filing | `sources/uscis_history.py` |
| *How Do I Request Premium Processing* | I-765 premium eligibility and the 30-business-day guarantee | `sources/uscis_premium.py` |

**The three reports slice Form I-765 three different ways**, which is the main
source of subtle bugs here:

| Slice | Quarterly | Backlog | Factsheet |
|---|:--:|:--:|:--:|
| Asylum | ✓ | ✓ | ✓ |
| Adjustment of status | ✓ | ✓ | ✓ |
| DACA | ✓ | ✓ | — |
| All other | ✓ | ✓ | ✓ |
| Parolees | — | ✓ | ✓ |
| Premium processed | — | ✓ | — |

Matching the reports on bucket name alone silently drops Premium Processed
(400 past target) and Parolees (16,500) and highlights the wrong trend line for
parole. `BUCKET_MAP` and `HISTORY_MAP` are therefore kept separate, and every
backlog row reaches the front end via `backlog_detail` whether or not it has a
quarterly counterpart.

### Premium processing

Only F-1 students in **(c)(3)(A), (c)(3)(B) and (c)(3)(C)** can request it on an
I-765. USCIS guarantees **adjudicative action within 30 business days** — around
six calendar weeks — or it refunds the fee. Two things the headline hides, both
stated in the UI:

* **Business days, not calendar days.** Reading it as "30 days" understates the
  window by roughly 40%.
* **Action, not approval.** An RFE satisfies the guarantee and stops the clock;
  responding starts a fresh 30-day period. Premium buys a fast decision *or a
  fast question*.

The **fee is deliberately not hardcoded.** It changed in 2026 and USCIS publishes
it only on its fee schedule, which isn't machine-readable — so the site links to
the schedule rather than printing a number that could go stale on a page someone
uses to make a four-figure decision. A test asserts no dollar amount is baked in.

Worth noting from the agency's own figures: **400** premium-processed I-765 cases
are past target, against **682,900** in "All other". The guarantee appears to
hold at scale.

URLs for the two XLSX reports are discovered from the USCIS data page each run,
so a new quarter is picked up automatically. The historical table is transcribed
rather than scraped — it's a fixed record in a PDF whose layout shifts between
releases — and `check_factsheet_available()` flags it in the build log if USCIS
moves the file.

**A trap worth recording:** USCIS also publishes an FY16–FY20 table that looks
like it could cross-check the factsheet. It can't. That page reports *national
averages* under a different category breakdown; the factsheet reports *medians*.
They disagree on every overlapping year by construction, so treating one as
validation for the other produces nothing but false alarms.

**Caveats, all surfaced in the UI:** figures lag by up to a quarter; USCIS
reports only four I-765 buckets, so OPT, STEM OPT, H-4 and L-2 share one number;
there's no service-center breakdown; and the historical series uses a cycle-time
methodology that isn't comparable to today's published figure — read its shape,
don't subtract it from current numbers.

### Reddit — supported in code, off by default, read this first

Reddit's [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy)
constrains this use case more than the "just make a script app" path suggests.
Four clauses matter here, and none of them are lawyer-speak edge cases:

1. **Approval is required** before accessing Reddit data through the API —
   registering an app is the start of that process, not a substitute for it.
2. **Sharing Reddit data needs express written approval.** The prohibition on
   selling, licensing or sharing Reddit data explicitly extends to
   *non-commercial* mining and scraping. Publishing a Reddit-derived dataset to
   GitHub Pages plausibly falls inside it, even though this project's output
   carries no usernames, comment text, or IDs.
3. **Research must go through the Reddit for Researchers program.** Research
   using Reddit data collected outside RFR is a policy violation, and aggregate
   processing-time analysis is research-shaped.
4. **Deriving sensitive characteristics about users is prohibited.** The policy's
   examples are health, political affiliation and sexual orientation, but the
   list is illustrative. **This project classifies commenters by immigration
   category — asylum pending, DACA, H-4 spouse.** That is squarely in the same
   family, and it is the clause I would worry about most.

**This repo therefore ships with Reddit disabled.** The published site consumes
only `official.json`; nothing in `docs/` reads Reddit-derived data. The scraper,
parser and survival code remain in the tree because they work and are useful
locally, but `--reddit` is opt-in and prints the policy reminder before running:

```bash
python -m scraper.build --reddit --max-threads 5 --save-raw
```

That writes `docs/data/dataset.json`, which **`.gitignore` does not cover** — if
you enable this, decide deliberately whether to commit it.

Remaining options if you want a real distribution:

* **Reddit locally, unpublished.** Useful for your own sanity-checking. Reduces
  (2) and (3); does not resolve (4).
* **Apply to RFR** if you want Reddit-derived analysis published.
* **Self-reported data.** Let users enter their own timelines — consented, no
  third-party platform terms in play. The cleanest route to a public
  distribution model, and the natural next feature for this project.

### USCIS Case Status API — deliberately unused

<https://developer.uscis.gov/api/case-status> is official, OAuth 2.0, and
generous (150k requests/day). But it is a **single endpoint keyed on a receipt
number, with no search or list capability**. Building a dataset from it would
mean enumerating receipt numbers to pull strangers' immigration records, which
this project will not do. It *is* a good fit for letting someone auto-track
their own case — one receipt number, entered by its owner.

This is a reading of the policy, not legal advice. The link above is the
authority; read it and decide.

### Reddit API setup (if you've decided to proceed)

Reddit blocks unauthenticated scraping — `www.reddit.com/*.json` returns **403**
from any datacenter IP, so this uses the official API. A free "script" app takes
about two minutes:

1. Go to <https://www.reddit.com/prefs/apps> → **create another app…**
2. Choose **script**. Name it anything; redirect URI `http://localhost:8080`.
3. Copy the **client id** (the string under the app name) and the **secret**.

Windows PowerShell:

```powershell
$env:REDDIT_CLIENT_ID="xxxxxxxx"
$env:REDDIT_CLIENT_SECRET="xxxxxxxxxxxxxxxx"
$env:REDDIT_USER_AGENT="script:ead-eta:1.0 (by /u/yourname)"
python -m scraper.build --max-threads 5
```

macOS / Linux:

```bash
export REDDIT_CLIENT_ID=xxxxxxxx
export REDDIT_CLIENT_SECRET=xxxxxxxxxxxxxxxx
export REDDIT_USER_AGENT="script:ead-eta:1.0 (by /u/yourname)"
python -m scraper.build --max-threads 5
```

`--max-threads 5` crawls only the busiest threads — a few minutes, good for a
first run. Drop the flag for a full crawl, which walks every discovered
megathread across all configured subreddits and can take 20–40 minutes; the free
tier's 100 requests/minute is the limiting factor, and `praw` throttles itself to
stay inside it.

Environment variables set this way last only for the current terminal. To
persist them, use `setx` on Windows or your shell profile elsewhere.

`scraper/config.py` holds the subreddits and the search queries used to discover
megathreads, so the crawler keeps working when mods roll a new thread. Add your
own threads to `SEED_THREAD_IDS`.

### On the other sources I tried

Worth writing down, because these are the obvious things to reach for and they
don't work the way you'd hope:

| Source | Status |
|---|---|
| `reddit.com/*.json` unauthenticated | **403.** Blocked outright. Use the OAuth API. |
| **PullPush** (Pushshift successor) | Archive **ends ~2025-05-19** — no recent data at all. Also rate-limits hard, returning *"This website does not provide free scraping resources for agents."* Left in as opt-in `--pullpush` for historical backfill, deliberately slow, and it gives up on 429 rather than retrying. |
| **USCIS `egov` processing-times API** | Cloudflare-gated by a **JS challenge**, not a TLS fingerprint check — plain `requests` fails and `curl_cffi` with a Chrome impersonation fails too. Not scriptable. Left in `sources/uscis.py` but unused by the default build. |
| `www.uscis.gov` bulk reports | Reachable, no Cloudflare. **This is what the project runs on.** |
| Community trackers (Trackitt, hilites.today, MyCasesHub) | Bigger samples than Reddit, but the same self-selection bias, and their terms generally prohibit scraping. Useful to eyeball against, not to ingest. |

---

## Deploying to GitHub Pages

1. Push the repo.
2. **Settings → Pages → Source: GitHub Actions.**

That's the whole setup. No secrets, no credentials — `.github/workflows/refresh.yml`
rebuilds weekly from public USCIS files and redeploys. A fork works immediately.

---

## Layout

```
scraper/
  config.py         EAD categories (+ Reddit search config, unused by default)
  parse.py          comment -> structured record (Reddit path only)
  survival.py       Kaplan-Meier, conditional curves (Reddit path only)
  build.py          fetch -> docs/data/official.json
  sources/
    uscis_bulk.py   quarterly volumes + net backlog  <- the default source
    uscis_history.py  FY2016-FY2024 median trend     <- the default source
    uscis_premium.py  I-907 premium processing rules <- the default source
    uscis.py        egov API (Cloudflare-blocked, unused)
    reddit_api.py   official OAuth API (opt-in, --reddit)
    pullpush.py     historical archive (opt-in, best effort)
docs/               the site — static, no build step, no dependencies
tests/
  test_parse.py     parser unit tests, no network
  test_official.py  bucket mapping + Little's Law, no network
  test_premium.py   premium rules + report-slicing asymmetry, no network
  validate_live.py  run the parser over a real thread and report hit rate
```

`docs/` reads only `official.json`. The Reddit modules are self-contained and
nothing in the site depends on them.

### Parser

The r/USCIS megathreads use a loose numbered template:

```
1. Application type: Post-OPT
2. Premium Processing: Yes
3. Receipt Date: 05/01/2025
4. Approved Date: 05/19/2025
```

Roughly half of real posts drift from it, so every field is matched by label
aliases scanned line by line, with a second looser pass for prose like *"I
applied for my STEM OPT on March 19, 2025"*. Against a real 1,189-comment
thread it extracted **186 usable records (16%)** — most of the remainder are
genuinely not timeline reports (`"F"`, questions, encouragement).

```bash
python -m pytest tests/ -q          # unit tests
python -m tests.validate_live       # hit rate against a live thread
```

---

## Limitations — read these

- **No percentiles, by design.** Aggregate counts can't yield a P80. The site
  shows two point estimates and says what each measures.
- **Little's Law assumes a steady state.** It gives a mean time in system for
  everything queued, including long-stuck cases, and adjudication isn't strictly
  FIFO. Read it as queue depth, an upper bound — not a median. The site reports
  each bucket's inflow ratio so you can see whether the assumption holds.
- **Coarse buckets.** USCIS reports four I-765 categories. OPT, STEM OPT, H-4 and
  L-2 all sit in "All other" and share one number.
- **National only.** No service-center breakdown in these reports.
- **Quarterly lag.** Figures trail real time by up to a quarter.
- **Mixed methodology.** The historical series uses cycle time; the current
  figure uses processing time. Compare shapes, not differences.
- **The past may not predict the future.** Policy changes, fee rules, and court
  decisions break the core assumption. A projection is not a promise.
- **Individual cases vary.** RFEs, background-check holds, and transfers are
  invisible to any aggregate model.
- **Not legal advice.** Not affiliated with USCIS.

---

## License

MIT — see `LICENSE`.
