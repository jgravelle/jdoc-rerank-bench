# A6 provisional class review — batch1 + batch2

**2026-09-20. Title-only judgment. No retrieval, no reranker, no Jev score was
consulted** (`LABEL-DESIGN-A6.md` §3.2, §3.3). Classes remain **provisional**
until the query-file freeze.

## What was done

320 drafts across four corpora were reclassified by re-running the heuristic in
`bench/a6_queries.py` and then applying a hand review of every title,
`queries/_draft/a6-class-review.json` (108 overrides, all of which matched a row).

| | Q2 | Q3 | Q4 | Q5 | Q6 |
|---|---|---|---|---|---|
| before | 83 | 183 | 14 | 26 | 14 |
| **after** | **31** | **178** | **37** | **15** | **59** |

| file | Q2 | Q3 | Q4 | Q5 | Q6 |
|---|---|---|---|---|---|
| batch1 packaging | 12 | 37 | 8 | 4 | 19 |
| batch1 pytest | 4 | 53 | 10 | 3 | 10 |
| batch2 fastapi | 4 | 51 | 8 | 5 | 12 |
| batch2 django | 11 | 37 | 11 | 3 | 18 |

## ⚠⚠ Two defects in the first heuristic, both found by reading the titles

**1. `LITERAL` matched the corpus's own name.** The pattern
`[A-Z][a-z]+[A-Z]\w*` matches **"FastAPI"**, so 54 of 80 fastapi titles were
classed Q2 — 68% of the corpus, on the strength of the framework being named in
its own questions. Django was untouched by the same bug only because "Django" has
no internal capital, which is why the counts looked plausible per-file and absurd
in aggregate. `TOPIC_NAMES` is now stripped before the literal test.

⚠ **A class distribution that looks wrong in one corpus and fine in another is
evidence about the classifier, not about the corpora.**

**2. "X vs Y" was Q5, and it is Q4.** "unittest vs pytest", "Model() vs
Model.objects.create()", "CharField vs TextField", "pip freeze vs pip list" are
all *which should I use* — policy. Reclassifying them is what thickened Q4 from 14
to 37, and it is a correction rather than a convenience: it is the reading the
class definitions in §3.5 support.

⚠ **It also starved Q5**, from 26 to 15, because those titles were most of what
the old rule had called multi-concept. The gap did not appear; it moved and became
visible. Q5 now means what it says: two doc ideas needed at once.

## Rules applied, so the next pass can disagree deliberately

Precedence **Q6 > Q4 > Q5 > Q2 > Q3**.

- **Q6** — the corpus's own docs cannot answer it. Third-party stack (docker,
  nginx, AWS, VS Code, PyCharm, conda, MongoDB, Angular, React, YouTube, OpenID),
  host OS and environment failures (`command not found`, `Access is denied`,
  `WinError`, `Microsoft Visual C++`, `clang error`, `port is already in use`,
  `ModuleNotFoundError`), or a question about a different library. This is why Q6
  went 14 → 59.
- **Q4** — policy, choice or constraint: *should / best / proper / correct way*,
  *is it bad to*, *when to*, *where to store*, project and directory structure,
  and any *A vs B* where the asker is choosing.
- **Q5** — genuinely two doc ideas: *both … and*, *while still*, *separate … from*,
  *integrate … with*, *together*, *at once*.
- **Q2** — a literal named API, flag, setting or dunder, **after** the corpus name
  is removed.
- **Q3** — everything else. A single fuzzy need, which is most of top-voted SO.

## ⚠⚠ The finding that matters for the study design

**Top-voted-by-tag Stack Overflow is a poor source for Q4 and Q5, and a rich
source of Q6.** Two structural reasons, neither fixable by reclassifying:

1. **Stack Overflow closes policy questions.** "Best practice" and "should I"
   questions are closed as opinion-based, so they rarely accumulate votes. Sourcing
   Q4 from top-voted SO fights the platform's own moderation.
2. **Top-voted questions are dominated by installation and environment failures.**
   Those are exactly the queries the rubric says must score every passage 0 ("if
   the documentation cannot answer the query at all, every passage is 0"), so they
   are Q6 controls, not ranking queries. 59 of 320 landed there.

Against `LABEL-DESIGN-A6.md` §2 floors for **dev + test combined** (30 test + 15
dev per ranking class):

| class | have | need | status |
|---|---|---|---|
| Q2 | 31 | 15 | OK |
| Q3 | 178 | 45 | OK, heavily over |
| Q4 | **37** | 45 | **short 8** |
| Q5 | **15** | 45 | **short 30** |
| Q6 | 59 | ~20 | OK, over |

**Q3 over-supply cannot be converted.** Relabelling a fuzzy single-need question
as Q5 to hit a floor would be fitting the strata to the target, which is the one
thing the class definitions exist to prevent.

## Integrity checks

| Check | Result |
|---|---|
| Rows | 320, all qids unique |
| Collision with the pre-batch1 spent set | **0** |
| Duplicate query text among drafts | **0** |
| Near-dup text vs spent (Jaccard ≥ 0.85) | 86 candidates dropped at fetch time |
| Override qids matching no row | **0** |
| Prefixes | `pt` packaging, `pyt` pytest, `fa6` fastapi, `dj6` django |

⚠ The spent set is recomputed live from `queries/**` and `labels/**` on every
fetch, so each batch also excludes the batches before it. `results/a6-spent-qids.txt`
is the pre-batch1 snapshot (541) and is **not** the live set.
