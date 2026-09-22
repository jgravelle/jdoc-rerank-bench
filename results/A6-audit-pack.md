# A6 human audit pack — audit-a6-2026-09-20

Generated 2026-09-21 from the labels committed at `dd9836d`. **The pack itself is
not tracked** (`.gitignore:9` excludes `audit/`), so this file is the only record
of what was asked and how. The gates come from LABEL-DESIGN-A6 section 7 and were
pre-registered before any label existed.

```
python -m bench.audit sample \
  --corpora django-a6test,fastapi-a6test,packaging-a6test,pytest-a6test \
  --per-corpus 100 --seed 0 --grade1-extra 40 --rubric a6 \
  --name audit-a6-2026-09-20
```

**440 items — 400 quota + 40 grade-1 oversample.** Per corpus, LLM grade 0/1/2:

| corpus | 0 | 1 | 2 | total |
|---|---|---|---|---|
| django-a6test | 30 | 46 | 35 | 111 |
| fastapi-a6test | 30 | 46 | 35 | 111 |
| packaging-a6test | 30 | 42 | 35 | 107 |
| pytest-a6test | 30 | 46 | 35 | 111 |

⚠ **packaging-a6test contributes 42, not 46, and it is not short.** It has exactly
42 grade-1 labels in total, so the oversample took all of them and the remaining
4 went to the other corpora round-robin. The pack total is the pre-registered 440.

## Two decisions this pack makes that the pre-registration left open

**Test corpora only, not dev.** Section 3 decides whether the A6 labels are
*evidence*; the dev split exists to tune against and is never scored. The
pre-registered cost estimate says "~100/corpus x 3-4", which is four corpora.

**The name keeps its registered date** while the pack was built on 2026-09-21. It
is an identifier, and an identifier that drifts from its registration is worse
than one that disagrees with the calendar.

## Gates (verbatim from section 7)

| | |
|---|---|
| LLM grade 0 | human says 0 in **>=90%** |
| LLM grade 2 | human says **1 or 2** in **>=80%** |
| LLM grade 1 | exact agreement + 0-vs-{1,2} confusion **reported**, not a hard kill; under **50%** exact is a STOP to revise the rubric |
| Fail action | fix guidelines, relabel, re-audit. A6 labels are not evidence until the gates pass |

⚠⚠ **The grade-2 gate is not exact agreement.** A human 1 counts, because grade 2
only has to be useful. Reading it as exact agreement fails a pass that section 3
accepts, and `bench/audit.py::agree` now prints the gate rather than leaving the
reader to derive it.

## What the auditor does

1. Read `audit/audit-a6-2026-09-20.md` (440 items, ~88,000 words). It carries the
   A6 rubric, the query, the heading path and the passage body. No grades.
2. Fill `human_grade` (0, 1 or 2) per row in `audit/audit-a6-2026-09-20.csv`.
   `note` is optional and free text.
3. **Do not open `audit-a6-2026-09-20.key.json` until the CSV is finished.** It
   holds the LLM grade for every item.
4. `python -m bench.audit agree --name audit-a6-2026-09-20`

Partial sheets are accepted and reported as `INCOMPLETE`: the strata are quota'd,
so skipped items bias whichever gate they belonged to, and a subset verdict says
so rather than reading as a pass.

---

# A6 dev audit pack — audit-a6dev-2026-09-21

Added 2026-09-21 on request, after the test pack. ⚠⚠ **This one is NOT
pre-registered.** Section 7 specifies a single audit and I read its scope as the
test split, because section 3 decides whether the labels are *evidence* and dev
exists to tune against. Dev is audited because it was asked for, and it carries
its own name and date so nobody later reads it as the registered pass.

```
python -m bench.audit sample \
  --corpora django-a6dev,fastapi-a6dev,packaging-a6dev,pytest-a6dev \
  --per-corpus 40 --seed 0 --grade1-extra 40 --rubric a6 \
  --name audit-a6dev-2026-09-21
```

**200 items — 160 quota + 40 grade-1 oversample.** 37,779 words.

| corpus | 0 | 1 | 2 | total |
|---|---|---|---|---|
| django-a6dev | 20 | 6 | 14 | 40 |
| fastapi-a6dev | 13 | 19 | 13 | 45 |
| packaging-a6dev | 12 | 26 | 14 | 52 |
| pytest-a6dev | 12 | 37 | 14 | 63 |

## ⚠⚠ Why `--per-corpus` is 40 here and 100 there

**Dev cannot support the registered size, and forcing it would have produced a
grade-0 pack wearing a stratified label.** Measured:

| corpus | pairs | g0 | g1 | g2 |
|---|---|---|---|---|
| django-a6dev | 75 | 55 | 6 | 14 |
| fastapi-a6dev | 180 | 148 | 19 | 13 |
| packaging-a6dev | 315 | 265 | 26 | 24 |
| pytest-a6dev | 630 | 492 | 71 | 67 |
| **dev total** | **1200** | **960** | **122** | **118** |

At `--per-corpus 100` the quota wants 35 grade-2 and 35 grade-1 from each. Three
of the four corpora cannot fill either, the allocator sends every shortfall to
grade 0, and the result is ~400 items dominated by grade 0 with all 240 non-zero
dev labels drained. 40 keeps the pack at **200 of 1200 (16.7%)**, against the
test pack's 440 of 2820 (15.6%) -- the same sampling rate, not a shrunken one.

## ⚠⚠ Five strata are a CENSUS, not a sample

| | |
|---|---|
| django-a6dev grade 1 | all 6 |
| django-a6dev grade 2 | all 14 |
| fastapi-a6dev grade 1 | all 19 |
| fastapi-a6dev grade 2 | all 13 |
| packaging-a6dev grade 1 | all 26 |

Two consequences, pulling opposite ways, and both belong in any write-up:

**The agreement rate for those strata is exact, not an estimate.** There is no
unsampled remainder for it to generalise to.

**⚠⚠ And there is no holdout, so "relabel and re-audit" turns circular.** The
section-7 fail action assumes unseen items exist to re-draw. For these five
strata a re-audit would re-judge the items already judged, which measures the
auditor's consistency and not the new labels. If a dev gate fails, the honest
remedy is a fresh dev draw, not a second pass over the same rows.

⚠ django-a6dev's grade-1 stratum is **6 items**. No gate should be quoted off it.
