# A6 sourcing, batch 4 — PRE-REGISTRATION

**Status: committed BEFORE any batch-4 fetch.** Authority: `DECISION_CRITERIA.md`
A6 + `LABEL-DESIGN-A6.md` §2 (floors) and §3 (sourcing rules). Approved by J.
2026-09-20 after the source-id exclusion put Q4 under its floor.

No pools, no labels, no Jev calls, no push.

## 1. Why batch 4 exists

`results/A6-spent-source-identity.md`: 95 of the 408 batch-1/2/3 drafts reuse a
Stack Overflow question already frozen in a prior split. The `qid` channel missed
them because a qid carries a per-batch prefix, and the Jaccard channel missed them
because a frozen split stores a hand-cleaned question while a fresh draw stores the
raw title. `spent()` now returns spent SOURCE question ids as a third channel.

**That exclusion is not negotiable and batch 4 does not revisit it.** It removed
95 rows and left **Q4 at 41 usable against a combined honest minimum of 42**
(test 30 + dev 12). Batch 4 restores the shortfall.

Usable after the exclusion, before batch 4:

| Class | Usable | Combined floor (test + dev) | Planned quota |
|---|---|---|---|
| Q2 | 22 | 15 | 18 |
| Q3 | 120 | 45 | 115–125 |
| Q4 | **41** | **45** | 55 |
| Q5 | 54 | 45 | 55 |
| Q6 | 76 | 10 | 20 |

## 2. Order of fill, fixed now

**Q4 first.** It is the only class under a floor. Q5 second, and only the 1 row it
needs to reach its planned quota plus slack. Q2 and Q6 are over their floors and
get **no batch-4 target at all**.

| Stratum | Usable | Batch-4 minimum | Batch-4 aim |
|---|---|---|---|
| Q4 | 41 | **+14** (to 55) | **+18** (to 59) |
| Q5 | 54 | **+1** (to 55) | **+6** (to 60) |
| Q2 | 22 | none | none |
| Q6 | 76 | none | none |

⚠ The +14 minimum is set against the **planned quotas** (test 35 + dev 20), not
against the honest minimum of 42. Sourcing only to the floor leaves an allocation
with no slack, and a single later exclusion puts it back under.

Cap: **~70 new drafts total.** Stop early once Q4 and Q5 both have slack.

## 3. Source preference, in order

1. **The batch-3 candidate cache first, at zero API requests.**
   `runs/a6-strat-cache/<corpus>.json` already holds the raw `/search/advanced`
   draw for the frozen batch-3 phrase lists. Measured 2026-09-20, after the
   source-id and Jaccard exclusions, it holds **1,034 unused Q4** (django 635,
   packaging 223, pytest 100, fastapi 76) and **241 unused Q5** (django 174,
   packaging 26, pytest 26, fastapi 15). ⚠ **The phrase lists in
   `A6-sourcing-batch3.md` §2 stay frozen** — reading further into the same draw
   is not a new draw, and re-fetching would spend quota to obtain the same rows.
2. **New `/search/advanced` calls** on the same frozen phrase lists, only for a
   (corpus, stratum) the cache cannot fill.
3. **GitHub Discussions** for `fastapi` and `pytest`, only if 1 and 2 leave a
   floor unmet. If used, the memo names which corpora took Discussions rows and
   how many.

## 4. ⚠⚠ Q3 is NOT topped up from the cache, and that is a disclosure decision

django's usable Q3 fell from 40 to **11** and fastapi's from 51 to **22**, because
those two corpora were drawn top-voted-by-tag — the same method that produced
`django-test*.jsonl` and `fastapi-test*.jsonl`, so a high collision rate was that
method's expected outcome. Their per-corpus ranking mass is now thin:

| Corpus | usable Q3 | Q4 | Q5 | ranking total |
|---|---|---|---|---|
| packaging | 34 | 12 | 12 | 58 |
| pytest | 53 | 15 | 16 | 84 |
| fastapi | 22 | 7 | 19 | 48 |
| django | **11** | 7 | 7 | **25** |

§2's "roughly even Q3–Q5 mass, about 30–45 ranking queries each" is an **aim**, not
a floor, and django will miss it.

The cache holds 488 unused rows that classify Q3, which would close the gap for
free. **They are not used.** Batch 3 §4 disclosed a specific mix: Q4 and Q5
phrase-filtered, Q3 and Q6 top-voted-by-tag. Drawing Q3 from a pool selected by Q4
and Q5 phrases would make Q3 a third, undisclosed subpopulation — rows that a
policy or multi-concept phrase caught and that then classified as neither. **A fix
that silences a disclosed skew by introducing an undisclosed one is the worse
trade.**

Two permitted routes for the Q3 aim, in order, both **aims with no floor attached**:

1. **Top-voted-by-tag at deeper pages** (`--start-page 6` onward) for django and
   fastapi, which is the same method Q3 already came from. Aim: django **+15**,
   fastapi **+8**. Pages 6+ were never drawn, so the collision rate should be lower
   than the shallow pages that produced the frozen splits.
2. **If those pages do not yield, the skew is DISCLOSED, not substituted.** The
   memo reports per-corpus ranking mass as measured and names django as
   under-powered for the per-corpus criterion in §6.

⚠ A thin corpus widens that corpus's confidence interval. It does not breach a
§2 floor, and it must not be reported as if it did — nor hidden.

## 5. Locks carried forward, unchanged

- **A phrase list selects CANDIDATES; it does not assign a class.** Every row is
  classified by `bench.a6_queries.classify` plus hand review. A row that does not
  classify into the stratum being filled is **dropped, never relabelled**.
- **No relabelling any other class to reach a floor.** Q3's surplus of 75 over its
  combined floor may not be spent on Q4 or Q5. Neither may Q6's 66 or Q2's 7.
- **Exclusions, all three channels, recomputed live at fetch time:** spent `qid`,
  near-duplicate text at token Jaccard ≥ 0.85, and **spent SOURCE question id**.
  Batch 4 therefore also excludes batches 1, 2 and 3.
- **Hand review is required** before any freeze. Batch 3's finding applies
  directly: **a phrase that selects a class also selects a failure mode for that
  class** — `together` and `integrate` pull in out-of-corpus integration questions
  (tox, poetry, South, Faust, Kafka, Keycloak, ReactJS, pytorch, BeautifulSoup,
  hypothesis) at about the rate they pull in genuine multi-concept ones. That draw
  took two review rounds and the first was discarded.
- **No peeking:** no retrieval output, no reranker ranking, no Jev score, no noul
  value, no A3 memo consulted to accept or reject any candidate, or to assign any
  class.
- New qid prefixes so provenance stays legible: **`pk4`** packaging, **`py4`**
  pytest, **`fa4`** fastapi, **`dj4`** django.
- Written to `queries/_draft/a6-batch4-<corpus>.jsonl`, same row schema, with
  `sourced` recording `batch4-cache` or `batch4-toptag`.

## 6. What batch 4 does to the pooled figure

Nothing new. Batch 3 §4 already binds the confirmatory memo: the split is
described as **stratified by title phrasing to meet class floors**, never as
"top-voted Stack Overflow questions"; per-class tables lead and the pooled figure
is not the headline; A6.4's pooled thresholds are applied to a constructed mix and
the memo says so beside the number.

Batch 4 draws from the same frozen phrase pool, so the mix does not change. ⚠ Any
Q3 rows taken under §4 route 1 are top-voted-by-tag, i.e. the method Q3 already
used, so they do not change it either.

## 7. Stop point

After batch 4: re-run `python -m bench.a6_freeze --check`.

- **If both A6-dev and A6-test floors pass**, freeze the query files, commit, and
  stop.
- **If they do not**, stop and report the shortfall. **The floors are not lowered
  to fit the corpus** — not quietly, and not with a note. Section 2's numbers were
  committed before any data and only J. changes them.

No pools, no labels, no push, no Jev.
