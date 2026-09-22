# A6 human audit — SECTION 3 FAIL, and the grader is why

Pack `audit-a6-2026-09-20`, 440 items, all graded by a human auditor (J.) over
eleven sittings. Blind throughout: the key was opened only after the 440th item.
Gates pre-registered in `LABEL-DESIGN-A6.md` section 7, before any label existed.

## Result

| Gate | Requirement | Measured | |
|---|---|---|---|
| LLM grade 0 | human says 0 in >=90% | **75.0%** of n=120 | **FAIL** |
| LLM grade 2 | human says 1 or 2 in >=80% | **90.0%** of n=140 | PASS |
| LLM grade 1 | reported; <50% exact is a STOP | **62.8%** exact of n=180 | reported, no STOP |

**SECTION 3: FAIL.** The A6 draft labels are **not evidence**. Nothing may be
scored against them — not Arm C, not Arm B, not a confirmatory delta.

Overall exact agreement 271/440 = **61.6%**. Binary "useful at all" agreement
**84%**.

## Confusion matrix

| | human 0 | human 1 | human 2 | n |
|---|---|---|---|---|
| **LLM 0** | 90 | 28 | 2 | 120 |
| **LLM 1** | 26 | 113 | 41 | 180 |
| **LLM 2** | **14** | 58 | 68 | 140 |

## ⚠⚠ It is not auditor drift, and that was tested before the key was opened

Two late blocks graded 60% and 62% grade 1 against 35-45% earlier, which raised
central-tendency drift as a live hypothesis mid-audit. **It was deliberately not
mentioned to the auditor**, because a warning at item 400 produces overcorrection
and an audit steered near the end is worth less than one with a known caveat.
Tested afterwards on the grade-0 gate by position:

| | grade-0 confirmations | rate |
|---|---|---|
| early, A001-A200 | 44/56 | 79% |
| late, A201-A440 | 46/64 | 72% |

Two-proportion **z = +0.85**. No significant drift, and **both halves fail the
90% floor independently**. The failure is uniform across the sheet.

⚠ The block-level grade mix DID vary (chi-square p wandered 0.09 to 0.42 across
the audit without settling). Grade mix varied; agreement did not. The blocks held
different material.

## ⚠⚠ The defect: topical adjacency read as answering

The disagreement is **not a severity gap**. Net signed difference is **-0.09 per
item** — the human is not systematically harsher or softer, and a threshold
adjustment would fix nothing.

The auditor's notes on the 14 worst cases (LLM said 2, human said 0) name one
failure repeatedly:

> "Explains type annotations that permit None, not how to replace an explicitly
> passed None"
> "Only mentions the OAuth2 `refreshUrl` metadata parameter; it does not implement
> or explain..."
> "pytest's cross-run cache is for plugin/fixture state, not a suitable
> source-controlled..."
> "This is ORM relation filtering, not locating an in-memory list element by an
> object's attribute"

**Each passage is about the query's topic and answers a different question.** An
8B model at temperature 0 scored same-topic as same-answer. That is the exact
confusion a retrieval benchmark exists to measure, so a grader with it cannot
produce labels for one.

### Where it concentrates

| corpus | grade-0 gate | | class | grade-0 gate |
|---|---|---|---|---|
| pytest-a6test | 87% | | Q2 | 100% (n=13) |
| fastapi-a6test | 77% | | Q4 | 80% |
| django-a6test | 73% | | Q3 | 73% |
| packaging-a6test | 63% | | Q6 | 67% |
| | | | Q5 | 63% |

Every corpus fails. Q2 (n=13) is the only clean class, and it is the class whose
queries are most literal.

## ⚠⚠ The rubric is not what failed

Grade-1 exact agreement is **62.8%, above the 50% STOP floor** — and above the
**43%** that A1's second-model audit produced on the OLD grade-1 wording. **The
tightened grade-1 rubric worked.** Rewriting guidelines is the wrong lever;
section 7's "fix guidelines" branch does not apply on this evidence.

What failed is grader capability at the 0/1 boundary.

## What this vindicates

⚠⚠ **A second-model audit would probably have passed this.** A3 already recorded
that a hosted judge graded against LLM-produced labels shares method bias the
harness cannot isolate. Two models with the same topical-similarity shortcut
agree with each other and call it validation. Section 7 required a human "not a
second model this time", and that requirement is the only reason this is known.

The audit cost eleven sittings and returned a negative result. That is the
cheapest 4,020-label mistake available.

## What happens next — and what does NOT

**The 440 human grades are now a gold validation set, and that changes the
economics.** Any candidate grader can be scored against them for 440 calls before
anyone spends 4,020. Required bar: the same section-7 gates, on the same items.

**Relabel with a stronger grader, then re-audit on a FRESH draw.** ⚠ Re-auditing
these 440 measures the auditor's consistency, not the new labels.

⚠⚠ **SUSPEND the dev audit (`audit-a6dev-2026-09-21`, 200 items).** Those labels
came from the same grader at the same temperature and will be replaced. Auditing
them now spends 200 items of human judgement on labels already known to be
discarded. **The pack stays on disk; it is not deleted and not run.**

**Arm B remains held**, now on both legs independently: the terms question
(addendum 2) and the confirmatory study having no valid labels. Even a written
"yes, publish" from TypeSafe would release nothing today.

⚠ The promo credits on the TypeSafe account expire **2026-10-20** with $4.74
left. If a confirmatory Arm B run is wanted, relabelling has to clear first.
