# LABEL-DESIGN-A6 — confirmatory Jev label plan

**Status:** FROZEN design (no labels collected yet; no Jev calls).
**Authority:** `DECISION_CRITERIA.md` amendment **A6** (commit ~`81d43fe` family) +
section 2 spirit + section 3 audit gate.
**Harness:** `C:\MCPs\jdoc-rerank-bench`, branch `exploratory-jev`.
**Product destination (after A6 SIGNAL only):** opt-in, off-by-default, BYOK Jev
in jDocMunch — not part of this file's execution.

**Non-goals of this document:** TypeSafe/Jev API spend, push to remote, secrets,
reopening Arm C ship, marketing claims.

Exploratory A3 SIGNAL justifies this study. It does **not** authorize ship.

---

## 0. Inventory snapshot (read-only; 2026-09-20)

| Piece | Where / what |
|---|---|
| Labelling | `bench/labeling.py` — blind export/collect; `GUIDELINES` grades 0/1/2 |
| Audit | `bench/audit.py` — `sample` (quota 2:35% / 1:35% / 0:30%, seed, per-corpus) + `agree` |
| Pools | `bench/pools.py` + `pools/<corpus>.n20.jsonl`; freeze via sha256 manifests |
| Spent A3 sets | `dev`: fastapi, k8s; `test`: k8s/fastapi/packaging/django-test; `test2`: +docker-test2 |
| Spent manifests | `pools-test.sha256` (4), `pools-test2.sha256` (5) — **never reuse for ship call** |
| Arm C (config-matched) | `Xenova/ms-marco-MiniLM-L-6-v2` `onnx/model_quantized.onnx`, 512 tok, 1/pass, 4 threads; pool 15; `promote(..., 0.95, k=10)` |
| Query source (prior) | Top-voted Stack Overflow (CC BY-SA), cleaned; classes Q2–Q6 |
| Prior grade-1 noise | Second-model audit: grade-1 exact agreement **43%** (A1 accepted as pass) |
| A3 shared-method bias | Grade-2 rubric ≈ paraphrase of Jev `true` — A6 forbids repeating that |

---

## 1. Corpora choice (locked)

**≥3 corpora, ≥1 new vs A3 spent, ≥1 policy-style.**

| Slot | Corpus id (proposed) | Role | Notes |
|---|---|---|---|
| C1 | `packaging` | **Policy-style** (kept) | packaging.python.org / PEPs — Q4-heavy; spent *query IDs* only, corpus retained |
| C2 | `fastapi` | Framework docs (kept) | Fresh query IDs only |
| C3 | `django` | Large RST docs (kept) | Fresh query IDs only; historically high regression under Arm C |
| C4 | `pytest` | **NEW vs A3 spent** | Not in A3 SETS; common agent/doc target; index under `corpora/pytest/` |

**Optional stretch (if time):** `k8s` with fresh IDs only — not required for the
minimum. Do **not** add docker unless a fifth corpus is needed for balance; docker
was already the A2 "new" corpus and showed weak oracle headroom.

**Honest minimum if cost/time constrained:** C1+C2+C4 only (packaging, fastapi,
pytest) still meets ≥3 / ≥1 new / ≥1 policy. Prefer the four-row table above.

All corpora use **new query IDs**. Any string that appears as `qid` in
`queries/*.jsonl` or `labels/*.jsonl` on this branch is **spent** and forbidden.
## 2. Target sizes (locked spirit; honest floors)

Section 2 / A2 / A6 want test ≥150 ranking queries with Q3–Q5 floors.

### A6-test (ship call)

| Stratum | Target | Honest minimum |
|---|---|---|
| Ranking Q3–Q5 pooled | **≥150** | 150 |
| Q3 (fuzzy) | ≥30 | 30 |
| Q4 (policy) | ≥30 | 30 |
| Q5 (multi-concept) | ≥30 | 30 |
| Q6 controls | ~20 (excluded from metrics) | ≥10 |
| Q2 (literal) | reported, not decided | ≥15 if cheap |

Per-corpus aim: roughly even Q3–Q5 mass (about 30–45 ranking queries each across four
corpora). Do not starve packaging Q4.

### A6-dev (T selection only; new)

| Stratum | Target | Honest minimum |
|---|---|---|
| Ranking Q3–Q5 pooled | **≥80** | 60 (record as underpowered if under 80) |
| Each of Q3, Q4, Q5 | ≥15 | ≥12 |

Dev is **only** for gated-promotion T grid under A6.4 (new grid bounds
pre-registered before any score). Dev queries must not appear in test.

**Why not reuse A3-dev:** configuration and selection optimism already touched
those labels; A6 requires a fresh confirmatory path.

---

## 3. Query sourcing rules (locked)

1. **Source:** Top-voted Stack Overflow questions tagged for the corpus topic
   (same family as prior splits), cleaned to a single developer question.
   Attribute CC BY-SA in the publishable set when numbers are ever published.
2. **No peeking at Jev:** no Jev scores, noul values, caches, or A3 memos used
   to accept/reject a candidate query.
3. **No peeking at rerankers for selection:** do not write or keep a query after
   looking at any reranker ranking for it. Class assignment (Q2–Q6) is from the
   question text + docs coverage judgment only.
4. **No spent IDs:** build an exclusion set from every `qid` in
   `queries/**/*.jsonl` and `labels/**/*.jsonl` before drafting. Also exclude
   near-duplicate question text (normalize whitespace/case; drop if Jaccard of
   tokens ≥ 0.85 against any spent query text).
5. **Class definitions (unchanged intent):**
   - Q2 literal token / exact API name
   - Q3 fuzzy / paraphrased need
   - Q4 policy / "what should I do when…" / constraints
   - Q5 multi-concept / needs ≥2 doc ideas
   - Q6 out-of-corpus control (docs cannot answer)
6. **Commit order:** queries → pool build → pool hash manifest → label tasks →
   labels → audit → **only then** any Arm C or Jev score on those pools.

---

## 4. Pool: hybrid top-15 freeze + hash

1. Build hybrid retrieval (`A-hyb`) pools with the **same embedder / hybrid
   settings** used for prior freezes (do not retune retrieval for A6).
2. Write `pools/<corpus>-a6dev.n20.jsonl` and `pools/<corpus>-a6test.n20.jsonl`
   (keep n20 files for compatibility; **judgment depth is top 15**).
3. Freeze judgment lists as `rankings["A-hyb"][:15]` per query (A6.4 / A3 pool).
4. Commit manifest **`pools-a6.sha256`** covering every A6 pool file (dev+test),
   same style as `pools-test.sha256` / `pools-test2.sha256` (sha256 of file
   bytes; verify before any score).
5. After the hash commit, pool files are immutable for the study. Relabeling
   requires a new hash filename (`pools-a6b.sha256`) and a post-hoc memo note.
## 5. Rubric (locked)

- **Grade 0 / 2:** unchanged text from `bench/labeling.py` GUIDELINES (still sound).
- **Grade 1:** **tightened** — full text in `results/RUBRIC-A6-grade1.md`.
- **Shared-method guard:** grade-2 wording must **not** be rewritten toward Jev
  A3 `true`. New Jev schema (later) must use a new schema id and non-paraphrase
  wording; that lock happens **after** labels freeze, in the scoring checklist.

Update `bench/labeling.py` GUIDELINES grade-1 line to point at / embed the
tightened definition **before** any A6 label export. Prefer embedding the full
grade-1 section so `python -m bench.labeling export` audit sheets stay
self-contained.

---

## 6. Labeling method (locked)

**Primary ship comparison is vs non-LLM Arm C (config-matched), not LLM-vs-LLM.**

| Layer | Who | Role |
|---|---|---|
| Draft labels | LLM OK (blind tasks from `bench.labeling export`) | Produce 0/1/2 under A6 rubric; temperature 0; note required |
| Optional dual draft | Second LLM **or** lightweight cross-encoder triage | Flag disagreements on grade-1 boundary for human priority |
| Freeze | `bench.labeling collect` → `labels/<corpus>-a6*.jsonl` | Commit before any A6 Arm C / Jev score |
| Audit | **Human** (J. or designee) — not a second model this time | Section 3 gates; see section 7 |

LLM draft labels are allowed **because** A6.4 makes the non-LLM baseline
decisive. Do not treat LLM–Jev agreement as evidence of retrieval quality.

---

## 7. Human audit sampling plan (section 3)

Use existing `python -m bench.audit sample` / `agree` machinery on A6 labels.

**Defaults (pre-register):**

| Knob | Value |
|---|---|
| Command | `python -m bench.audit sample --corpora <a6 list> --per-corpus 100 --seed 0 --name audit-a6-2026-09-20` |
| Quota | keep `QUOTA = {2: 0.35, 1: 0.35, 0: 0.30}` |
| Grade-1 oversample | After default sample, add **+40** grade-1 items (round-robin across corpora/queries) into the same audit pack so the noisy stratum is judged with more power |
| Auditor | Human; blind `audit-*.md` / `.csv`; do not open `.key.json` first |
| Gates (section 3) | LLM grade 0 → human says 0 in ≥**90%**; LLM grade 2 → human says 1 or 2 in ≥**80%** |
| Grade-1 report | Exact agreement + 0-vs-{1,2} confusion **reported**; not a hard kill by itself, but if grade-1 exact agreement is under 50% after the tightened rubric, **stop and revise rubric** before scoring |
| Fail action | Fix guidelines, relabel, re-audit; A6 labels are not evidence until gates pass |

A1's second-model audit does **not** carry over. A6 needs a human pass.

---

## 8. Non-LLM baseline to freeze (Arm C config-matched)

Reproduce beside Jev; **decisive** for A6.4 primary evidence with hybrid.

| Knob | Freeze |
|---|---|
| Model | `Xenova/ms-marco-MiniLM-L-6-v2` |
| File | `onnx/model_quantized.onnx` (int8) |
| Tokens | 512 |
| Batch | **one passage per inference call** (A1) |
| Threads | 4 onnxruntime |
| Pool | hybrid top **15** |
| Transform | `bench.tune.promote(pool, scores, 0.95, k=10)` — byte-identical |
| Passage text | `bench.providers.passage_text(c, metadata=True)` (same string family as A3) |
| Metrics | nDCG@5 vs `A-hyb`, Q3–Q5; all-grades worse %; bootstrap 5k seed 0 |

Do **not** retune Arm C's 0.95 on A6-dev. A6-dev T grid is for **Jev only**.
## 9. Ordered execution checklist (stop points)

**STOP means: do not proceed; no Jev; no Arm C score on A6 pools.**

1. [ ] Commit this file + `RUBRIC-A6-grade1.md` on `exploratory-jev`.
2. [ ] Update `bench/labeling.py` GUIDELINES grade-1 to A6 text; unit-smoke export.
3. [ ] Build spent-qid + spent-text exclusion list from all existing queries/labels.
4. [ ] Index `pytest` corpus (and confirm packaging/fastapi/django indexes).
5. [ ] Collect **first batch of queries** (see section 11) — SO fetch, clean, classify, exclude spent.
6. [ ] Freeze A6-dev query files; commit.
7. [ ] Freeze A6-test query files; commit. **STOP** if floors in section 2 unmet.
8. [ ] Build hybrid pools (n20 files); confirm top-15 judgment depth.
9. [ ] Write + commit `pools-a6.sha256`. **STOP** — pools immutable.
10. [ ] `labeling export` → draft LLM labels under A6 rubric → `collect` → commit labels.
11. [ ] Human audit sample (+ grade-1 oversample) → fill CSV → `audit agree`.
12. [ ] **STOP** unless section 3 gates pass (and grade-1 sanity in section 7).
13. [ ] Pre-register Jev T grid bounds + **new** non-paraphrase schema id/wording (separate short doc). **Still no Jev calls.**
14. [ ] Score Arm C config-matched on frozen A6 pools (local; $0 API).
15. [ ] Only then: Jev scoring / determinism / latency under **$40** wall (A6.4).
16. [ ] Apply A6.5 stop rule; write `CONFIRMATORY-jev-…` memo (not EXPLORATORY).

**Hard rule:** no Jev until steps 1–12 are done and committed in that order.

---

## 10. Cost & human hours (estimates)

### Human time

| Phase | Hours (estimate) |
|---|---|
| Query collect + classify (dev+test, 4 corpora) | 6–10 |
| Pool build / hash / bookkeeping | 1–2 |
| Rubric dry-run on 30 items + LLM prompt bake | 2–3 |
| Human audit (~100/corpus × 3–4 + 40 grade-1) | **8–14** |
| Memo / criteria hygiene | 2–3 |
| **Total** | **≈20–30 h** |

### Later API $ (Jev scoring phase only — must fit under **$40**)

Prior A3 screen: ~7,380 pairs ≈ 5.2M input tokens ≈ **$0.22** at published
$0.042/Mtok (output free). A6-dev (~80–100 × 15) + A6-test (~150 × 15) ≈
3.5k–4k pairs plus determinism (~100 pairs × 2) and latency pools → well under $5
expected at that rate. **$40 wall** remains the hard stop; ask J. before any
extension. Labeling LLM draft spend is separate and should use a cheap local or
already-budgeted model — not TypeSafe.

Arm C scoring: $0 (local ONNX).

---

## 11. Exact next command/step (first query batch)

On MegaBoxen3000, from `C:\MCPs\jdoc-rerank-bench` on `exploratory-jev`:

```powershell
# 1) Build spent exclusion set (QIDs + normalized query texts)
$env:PYTHONPATH = '.'
python -c @"
import json, re
from pathlib import Path
root = Path('.')
spent_qids, spent_texts = set(), set()
def norm(s):
    return re.sub(r'\s+', ' ', s.lower()).strip()
for p in list(root.glob('queries/**/*.jsonl')) + list(root.glob('labels/**/*.jsonl')):
    for line in p.read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        if 'qid' in r: spent_qids.add(r['qid'])
        if 'query' in r: spent_texts.add(norm(r['query']))
Path('results/a6-spent-qids.txt').write_text('\n'.join(sorted(spent_qids)), encoding='utf-8')
Path('results/a6-spent-texts.txt').write_text('\n'.join(sorted(spent_texts)), encoding='utf-8')
print('spent_qids', len(spent_qids), 'spent_texts', len(spent_texts))
"@

# 2) First batch: packaging + pytest SO candidates (policy + NEW corpus)
#    Reuse the prior SO fetch pattern (tagged top-voted; exclude spent texts).
#    Write drafts under queries/_draft/a6-batch1-packaging.jsonl and
#    queries/_draft/a6-batch1-pytest.jsonl — NO pools, NO labels yet.
```

Then classify Q2–Q6 by hand/LLM-assist **without** retrieval scores, drop
spent/near-dupes, and commit only when packaging drafts clear a path to the
Q3–Q5 floors in section 2.

---

## 12. Decisions still needing J. / Grok Bot

1. **Confirm new corpus = `pytest`** (alt: pydantic / click / redis) before indexing.
2. **Four corpora vs honest minimum three** (drop django?).
3. **Who is the human auditor** for section 3 (J. vs delegate) and calendar block
   for ~8–14 h.
4. **LLM used for draft labels** (provider/model pin) — must not be Jev.
5. **Jev schema rewrite** (post-label freeze): approve non-paraphrase wording +
   new schema id before any confirmatory Jev call.
6. Executor on this pass could not reach MegaBoxen3000 via machineId Shell /
   CopyToBox from the box subagent; parent should verify the commit landed on
   `exploratory-jev` at the path below.

---

## 13. Deliverable paths

- `results/LABEL-DESIGN-A6.md` (this file)
- `results/RUBRIC-A6-grade1.md` (tightened grade 1)

Commit message (when applied on the Windows harness):

docs(A6): confirmatory label design + grade-1 rubric
