# A6 §9 step 6/7 REFUSED: the spent set did not identify a question

**2026-09-20, branch `exploratory-jev`. No pools, no labels, no Jev call. Nothing
was written to `queries/`.**

## What happened

Freezing A6-dev and A6-test from the reviewed drafts refused at the feasibility
check. The cause is not the split arithmetic; it is that **95 of the 408 reviewed
drafts reuse a Stack Overflow question that is already frozen in a prior split.**

`LABEL-DESIGN-A6.md` §3.4 asks for two exclusions: no spent `qid`, and no
near-duplicate query text at Jaccard ≥ 0.85. Both were implemented and both ran.
Neither identifies a question.

- **The qid channel is defeated by the prefix.** A qid is `<prefix><question_id>`
  and the prefix is chosen per batch. `dt8609192` (frozen in `django-test.jsonl`)
  and `dj68609192` (batch-2 draft) are the same question under two prefixes, so
  the set membership test never fires. Batch 1 also drew packaging under prefix
  `pt`, which is the prefix `packaging-test.jsonl` already uses — so that batch
  was one collision away from a genuinely ambiguous qid.
- **The text channel is defeated by our own cleaning.** §3.1 says candidates are
  "cleaned to a single developer question", and the frozen splits carry that
  cleaned wording while a fresh draw carries the raw SO title. Two wordings of one
  question routinely fall under 0.85. It caught **2 of the 95**.

⚠⚠ **Two independent exclusions agreeing that a row is fresh is not evidence,
because both were keyed on a name we assign rather than on the thing named.** The
`source` field carried the real identity the whole time and nothing read it.

## Impact on the drafts

| Class | Drafted | Spent-source | Usable |
|---|---|---|---|
| Q2 | 31 | 9 | 22 |
| Q3 | 180 | 60 | 120 |
| Q4 | 58 | 17 | **41** |
| Q5 | 58 | 4 | 54 |
| Q6 | 81 | 5 | 76 |
| total | 408 | 95 | 313 |

By corpus: django 51, fastapi 41, packaging 3, pytest 0. The two batch-2 corpora
were drawn from top-voted-by-tag, which is the same draw that produced
`django-test*.jsonl` and `fastapi-test*.jsonl`, so a high overlap was the expected
outcome of that method and nothing measured it.

Usable per corpus:

| Corpus | Q2 | Q3 | Q4 | Q5 | Q6 |
|---|---|---|---|---|---|
| packaging | 12 | 34 | 12 | 12 | 29 |
| pytest | 4 | 53 | 15 | 16 | 14 |
| fastapi | 2 | 22 | 7 | 19 | 11 |
| django | 4 | 11 | 7 | 7 | 22 |

## Why this is a STOP, not a smaller split

§2's floors are test Q3/Q4/Q5 ≥ 30 each with ≥ 150 pooled, and dev ≥ 12 each
(≥ 15 target) with ≥ 60 pooled (≥ 80 target).

**Q4 has 41 usable against a combined honest minimum of 42** (test 30 + dev 12),
and against the planned 55 (test 35 + dev 20). Q3 and Q5 clear their floors but
sit under target. Pooled ranking availability is 215 against the 210 both splits
need at their floors, i.e. 5 of slack across three strata.

Freezing dev alone would not help: dev drawing 12–15 Q4 leaves test with 26–29,
under its own floor. **Test is the binding constraint and must be allocated
first**, so the correct order is to source more Q4 and then freeze both splits in
one pass.

Per-corpus evenness is also gone at the same time: django's whole usable ranking
mass is 25 (11 + 7 + 7) across both splits, against §2's "roughly even Q3–Q5 mass,
about 30–45 ranking queries each" for test alone.

## What was changed here

- `a6_queries.spent()` returns a **third channel**, the set of spent SOURCE
  question ids, and `source_id()` reads it from `source`. Both fetch paths
  (`a6_queries.cmd_fetch`, `a6_strat`) now exclude on it. ⚠ Purely subtractive:
  it can only remove candidates, never admit one, so it cannot loosen a floor. The
  frozen phrase lists of `A6-sourcing-batch3.md` are untouched.
- `bench/a6_freeze.py` is the freeze tool: deterministic allocation, a feasibility
  report against §2's floors, and a refusal that names the short stratum. It
  excludes spent-source rows on every run and prints the count, so the drafts stay
  the raw record and the discrepancy with `a6-class-review.md` is always visible.

⚠ **The drafts were NOT edited.** Removing the 95 rows from
`queries/_draft/*.jsonl` would destroy the evidence for this file's own table.

## What is needed to reach the floors

The batch-3 candidate cache under `runs/a6-strat-cache/` already holds, at **zero
API requests** and after the corrected identity rule, **1,034 unused Q4** and
**241 unused Q5** candidates: Q4 by corpus django 635, packaging 223, pytest 100,
fastapi 76. So the shortfall is reachable without spending quota.

⚠ It is not free of REVIEW, and batch 3's finding applies directly: **a phrase
that selects a class also selects a failure mode for that class.** The `together`
and `integrate` phrases pull in out-of-corpus integration questions at about the
rate they pull in genuine multi-concept ones, which is why that draw took two
hand-review rounds and the first was discarded.

**Not started. A batch-4 draw is new sourcing and is outside the authorised step.**
