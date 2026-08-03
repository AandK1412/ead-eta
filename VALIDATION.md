# Validation

Cross-reference of this project's figures against independent reporting.
Run `python -m tests.cross_reference` to regenerate the computed side.

**Checked:** 2026-08-03 · **Our data:** USCIS FY2026 Q1 (1 Oct – 31 Dec 2025)

---

## What we compute

| Metric | Value |
|---|---|
| Total I-765 pending | 1,621,190 |
| Pending past USCIS's own target | 969,400 (59.8%) |
| Received per quarter | 591,127 |
| Completed per quarter | 590,309 (inflow ratio **1.00×**) |
| Published processing time, completion-weighted | **2.3 months** |
| Backlog-implied wait, pending-weighted | **15.2 months** |

## What independent reporting says

Multiple immigration-law sources, reporting on February 2026 (two months after
our quarter closes):

| Metric | Reported |
|---|---|
| I-765 pending | ~1,780,000 |
| Pending waiting longer than 6 months | ~1,180,000 (**66.3%**) |
| Average processing time, all categories | **4.8 months**, up from a 2.5-month low the previous summer |

Practitioner ranges by category: OPT 2–5 months (online filings 2–3), H-4 EAD
6–12+, adjustment of status 3–8, F-1 around 4.5.

---

## Verdict

### ✅ Volume and backlog corroborate strongly

Pending of 1.62M (Dec 2025) against ~1.78M (Feb 2026) is the right order of
magnitude and the right direction. Our 59.8% "past USCIS's target" sits close to
the independently reported 66.3% "waiting over six months" — different
definitions, same picture, and both moving the same way.

### ⚠️ The backlog-implied figure overshoots

Our pending-weighted 15.2 months is roughly 3× the reported 4.8-month average
and above even the slowest practitioner category (H-4 at 6–12+ months). Little's
Law is doing what the README warns it does: the pending pool contains a long
tail of stuck cases, adjudication isn't FIFO, so `pending ÷ throughput`
overstates what a typical new filer experiences.

**It should be read as an upper bound, never as a point estimate.** The site
labels it that way; this confirms the label is necessary rather than decorative.

### ✅ …but the project's core claim survives, and this data sharpens it

The published figure genuinely understates the queue, and there is now a clean
independent way to prove it:

> **66% of pending cases have been waiting more than six months, while USCIS
> publishes ~4.8 months as the typical wait.**

Those two facts cannot both describe the same population. If the central wait
really were under five months, two-thirds of the queue could not already be past
six. The published number describes cases that *finished*; the backlog describes
the queue you are actually standing in.

**Best reading of the truth:** the central wait for the aggregate sits somewhere
in the **6–12 month** range — above the published 4.1–4.8, well below the
backlog-implied 15–17. Neither bar in the chart is the answer; the answer is
between them, and the chart now says so.

### ❓ Open discrepancy: pending grew far faster than our flows predict

Pending went from 1.62M to ~1.78M in about two months — roughly **+79,000 per
month**. Our Q1 flows show receipts and completions almost exactly balanced
(591,127 vs 590,309, i.e. **+273 per quarter**). Those cannot both be right.

Candidate explanations, untested:

1. Flows changed sharply after December 2025 — an inflow surge or a drop in
   adjudication capacity. Plausible; the reported jump from a 2.5-month low the
   previous summer to 4.8 months by February suggests something did shift.
2. The external 1.78M is measured on a different basis (a different snapshot
   date, or a scope that isn't exactly the four I-765 buckets).

**This resolves when FY2026 Q2 publishes.** If Q2 shows an inflow ratio well
above 1.0, explanation (1) holds and the backlog-implied figure will rise for
good reason. Worth re-running this check then.

---

## Sources

- [I-765 processing times, 2026](https://manifestlaw.com/blog/i765-processing-time) — Manifest Law
- [OPT processing time 2026](https://www.trackmyopt.com/blog/opt-processing-time-2026) — TrackMyOPT
- [I-765 EAD processing guide 2026](https://www.casestatusapi.com/guides/i-765-ead-processing-guide) — CaseStatusAPI
- [USCIS processing times tracker 2026](https://lawofficeimmigration.com/tools/processing-time-tracker.html) — Modern Law Group
- [OPT processing time 2026](https://immiva.com/blog/opt-processing-time-2026) — Immiva
- Our figures: [quarterly form data](https://www.uscis.gov/sites/default/files/document/reports/quarterly_all_forms_fy2026_q1_v1.xlsx)
  and [net backlog](https://www.uscis.gov/sites/default/files/document/reports/net_backlog_frontlog_fy2026_q1_v1.xlsx), USCIS

Secondary sources are law-firm and tracker blogs, not primary data. They agree
with each other and with the USCIS totals, which is why they're usable as a
sanity check — but they are not independent of one another in any strong sense.
