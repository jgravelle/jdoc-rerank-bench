# A6 sourcing, batch 3 — PRE-REGISTRATION

**Status: committed BEFORE any batch-3 fetch.** Authority: `DECISION_CRITERIA.md`
A6 + `LABEL-DESIGN-A6.md` §2 (floors) and §3 (sourcing rules). Approved by J.
2026-09-20 after batch 1 + 2 left Q4 and Q5 under their floors.

No pools, no labels, no Jev calls, no push.

## 1. Why batch 3 exists

Batches 1 and 2 sourced top-voted-by-tag Stack Overflow. That produced 178 Q3 and
59 Q6 against floors of 45 and ~20, and left **Q4 at 37 (need 45)** and **Q5 at 15
(need 45)**. Two structural reasons, recorded in `results/a6-class-review.md`:

1. Stack Overflow closes "best practice" and "should I" questions as
   opinion-based, so policy questions rarely accumulate votes.
2. Top-voted questions are dominated by install and environment failures, which
   the rubric scores as all-zero, i.e. Q6 controls rather than ranking queries.

**Top-voted-by-tag alone cannot reach the Q4 and Q5 floors.** Batch 3 therefore
samples those two strata from a phrase-filtered pool.

## 2. Sources, fixed now

**Primary: Stack Exchange `/2.3/search/advanced`**, one request per (tag, phrase),
`sort=votes&order=desc`, matching on **`title=`** so selection uses only the text
we also classify from.

**Contingency: GitHub Discussions** for `fastapi` (`fastapi/fastapi`) and `pytest`
(`pytest-dev/pytest`), used **only if** the SO pass leaves a floor unmet. The
harness already has this precedent: the A3 FastAPI dev split drew on FastAPI
GitHub Discussions (recorded in `README.md`). If used, the memo names which
corpora took Discussions rows and how many.

### Tags per corpus

| Corpus | Tags |
|---|---|
| packaging | `pip`, `python-packaging` |
| pytest | `pytest` |
| fastapi | `fastapi` |
| django | `django` |

### Title phrases, frozen before the fetch

**Q5 (needs ≥2 doc ideas):** `both`, `together`, `combine`, `integrate`,
`as well as`, `while still`, `at the same time`, `separate`

**Q4 (policy / choice / constraint):** `best practice`, `best way`, `should i`,
`recommended`, `proper way`, `when to use`, `convention`, `vs`,
`difference between`

⚠ These lists do not change after this commit. A phrase that yields nothing
yields nothing.

## 3. ⚠⚠ A phrase list selects CANDIDATES; it does not assign a class

Every fetched row is classified by the **same** rule as batches 1 and 2
(`bench.a6_queries.classify` plus the hand review). A title containing "both" is
not thereby Q5. Rows that do not classify into the stratum being filled are
**dropped, not relabelled**.

**No relabelling Q3 → Q5 (or → Q4) to reach a floor.** This is the lock the class
definitions exist to protect, and batch 3 is the step where it would be tempting.
Q3 currently has a surplus of 133 and none of it may be spent.

## 4. ⚠⚠ What this does to the pooled figure, disclosed in advance

Batch 3 draws Q4 and Q5 from a phrase-filtered pool while Q3 and Q6 come from
top-voted-by-tag. **The strata therefore have different inclusion probabilities,
so the Q3–Q5 pooled number is a figure about a mix we constructed, not an estimate
of performance on the real distribution of user questions.**

Consequences, binding on the confirmatory memo:

- The split is described as **stratified by title phrasing to meet class floors**,
  never as "top-voted Stack Overflow questions".
- **Per-class tables lead; the pooled figure is not the headline** (already A6 §10
  / section 10 of the criteria).
- A6.4's pooled thresholds (point ≥ +0.04, lower bound > 0, worse ≤ 12%) are
  applied to that constructed mix, and the memo says so beside the number.

This does not weaken the *comparison* between arms — every arm sees the same
queries — but it does bound what the absolute figures describe.

## 5. Targets and caps

Fill **Q5 first**, then Q4.

| Stratum | Have | Need (30 test + 15 dev) | Batch-3 target |
|---|---|---|---|
| Q5 | 15 | 45 | **+30 minimum**, aim +36 for slack |
| Q4 | 37 | 45 | **+8 minimum**, aim +14 for slack |

- Cap: **~100 new drafts total**; stop early once both floors have slack.
- Written to `queries/_draft/a6-batch3-<corpus>.jsonl`, same row schema.
- Aim for spread across corpora rather than one corpus carrying a stratum; record
  the per-corpus histogram either way.

## 6. Exclusions, unchanged from §3.4

- Spent qids recomputed **live** from `queries/**` and `labels/**` at fetch time,
  so batch 3 also excludes batches 1 and 2.
- Near-duplicate text dropped at token Jaccard **≥ 0.85** against every spent
  query text.
- New qid prefixes so provenance stays legible: `pk3` packaging, `py3` pytest,
  `fa3` fastapi, `dj3` django.
- No retrieval, no reranker output, no Jev score, no A3 memo consulted to accept
  or reject any candidate.

## 7. Django corpus — resolved, not dropped

Lock 3 asked for a pinned SHA or removal. **A pinned snapshot was reproduced, so
django stays.**

`corpora/django-rst` was a *derived* directory with no SHA: django/django `docs/`
with `.txt` renamed to `.rst`. The derivation was recovered exactly:

```
git clone --depth 1 https://github.com/django/django.git django-src   # 446d9cf6…
cp -r django-src/docs django-a6
find django-a6 -name '*.txt' -> rename to .rst
rm django-a6/README.rst        # upstream ships this as .rst; the A3 dir omits it
```

**Verification:** the resulting file set is **identical** to `corpora/django-rst`
(677 `.rst` files, `diff` of the sorted path lists is empty). That is what makes
the procedure "known" rather than guessed.

| | |
|---|---|
| Corpus dir | `corpora/django-a6` |
| Snapshot SHA | **`446d9cf602a5c42862da118b714a5679bb61cf27`** (2026-09-19) |
| Index name | **`local/django-a6`** |

⚠ Indexed under a **new name** on purpose: re-indexing `local/django` would
overwrite the A3 index and destroy the ability to rebuild A3's pools. The A3
`django` index is left untouched.

⚠ The A3 memos recorded django at `935edaa91b756325352ca70d5eba49a64b70d28c`.
The A6 snapshot is a **different, newer** commit. A6 requires fresh everything, so
this is correct, but the two studies are not on the same django text and no
cross-study django comparison may be drawn.

## 8. Stop point

After batch 3: report updated histograms and state plainly whether the test and
dev floors are reachable. **No pools, no labels, no push, no Jev** until J. says so.
