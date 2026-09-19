# Decision memo — jDocMunch local reranker, test split

Date: 2026-09-19. Criteria: `DECISION_CRITERIA.md` at `074dfa3`, plus amendment
A1 (`97ff17e`, post hoc, committed before any test-split score existed).

## Verdict: ITERATE

The gain is real and replicated. Two of the five ship checks fail, so the local
reranker does not ship on this evidence. No kill condition is met.

## Order of events, from the harness history

| Commit | What |
|---|---|
| `074dfa3` | Criteria in force |
| `0be914e`, `d767b04` | Test queries; sha256 of the four frozen pool files |
| `97ff17e` | Amendment A1 |
| `c4bf47b` | Test labels frozen (5,788 pairs). Pool hashes re-verified first. |
| `e4c21f7` | Evaluator (`bench/decide.py`) and the provider config |
| after that | First and only reranker scoring of the test split |

## Setup

- 185 ranking queries and 20 out-of-corpus controls, all Stack Overflow questions
  in vote order, selected from titles alone. Four corpora: Kubernetes, FastAPI,
  Django (new), Python Packaging User Guide with the PyPA specifications (new,
  policy-style). The decision set is Q3 to Q5: 154 queries.
- Baseline `A-hyb`: jdocmunch `121a5a2`, hybrid search, `sentence-transformers`
  embedder, top 20.
- Reranker: `Xenova/ms-marco-MiniLM-L-6-v2`, `onnx/model_quantized.onnx`, 512
  tokens, one passage per call, 4 threads, torch not loaded. RRF k=60.
- Labels: blind LLM grades 0/1/2. **The audit was done by an independent second
  model, not a human.** J. accepted it as a pass under A1. Its weak stratum was
  grade 1 (43% exact agreement), which is why the sensitivity table exists.
- Django's docs are RST in `.txt` files. They were copied to `.rst` so jdocmunch
  used its RST parser. Nothing in jdocmunch changed.
- The 4-thread cap is not fixed by the criteria. It was my choice, from the
  deployment sketch.

## Results, nDCG@5, paired delta against `A-hyb`

| Group | n | Baseline | Oracle gain | Delta [95% CI] | Better | Worse | Worse % |
|---|---|---|---|---|---|---|---|
| Q3 (fuzzy) | 76 | 0.334 | +0.549 | +0.128 [+0.080, +0.172] | 44 | 10 | 13.2% |
| Q4 (policy) | 42 | 0.482 | +0.421 | +0.072 [+0.019, +0.123] | 24 | 6 | 14.3% |
| Q5 (multi-concept) | 36 | 0.402 | +0.476 | +0.059 [+0.008, +0.113] | 19 | 7 | 19.4% |
| Q2 (literal token), not decided on | 31 | 0.414 | +0.571 | +0.200 [+0.124, +0.282] | 24 | 2 | 6.5% |
| Kubernetes | 43 | 0.371 | +0.528 | +0.106 [+0.061, +0.154] | 25 | 3 | 7.0% |
| Packaging | 36 | 0.377 | +0.436 | +0.138 [+0.073, +0.205] | 23 | 4 | 11.1% |
| Django | 43 | 0.417 | +0.517 | +0.078 [+0.023, +0.132] | 22 | 10 | 23.3% |
| FastAPI | 32 | 0.397 | +0.497 | +0.062 [-0.020, +0.129] | 17 | 6 | 18.8% |
| **Q3 to Q5 pooled** | 154 | 0.391 | +0.497 | **+0.097 [+0.066, +0.126]** | 87 | 23 | **14.9%** |

Sensitivity, only grade 2 counts as relevant: pooled +0.093 [+0.060, +0.125],
58 better, 8 worse (5.2%). Every corpus and class keeps its sign. The full
table is in `results/test-split-2026-09-19.md`.

Latency, one pool of 20, CPU: p50 398 ms, p95 1,251 ms, max 2,019 ms (n=205).
Per corpus p50 / p95: Kubernetes 289 / 581, FastAPI 511 / 679, packaging
375 / 973, Django 828 / 1,671.

Out-of-corpus controls: median top reranked score 0.819 on the 20 controls,
0.980 on the 185 answerable queries.

## Section 6, quoted and applied

> 1. Pooled delta: lower bound of the interval above zero, and point estimate at
>    least **+0.04**

**PASS.** +0.097, lower bound +0.066.

> 2. Every corpus: point estimate above zero. No corpus with an interval entirely
>    below zero.

**PASS.** All four points are positive. FastAPI's interval includes zero
[-0.020, +0.129], which the criterion allows.

> 3. Regressions: at most **12%** of queries have a lower nDCG@5 than baseline.

**FAIL.** 23 of 154, 14.9%.

> 4. No query class in Q3 to Q5 with an interval entirely below zero.

**PASS.** All three class intervals are entirely above zero.

> 5. Latency: p95 at most **500 ms**, p50 at most **300 ms**

**FAIL.** p50 398 ms, p95 1,251 ms.

> 6. Out-of-corpus controls: the top reranked score on Q6 queries is reported.

Reported above. The medians differ, and the control median is still high
(0.819), so a plain score threshold would not separate "nothing relevant" well.

## Sections 8 and 9 applied

> - Gain is real but section 6.3 fails: tune the fusion on dev, then a NEW test
>   split. The spent one cannot be reused.
> - Gain is real but 6.5 fails: pool of 15, then re-test.

Both apply. This test split is spent.

Kill: the pooled lower bound is above zero; latency at pools of 10 and 15 was
not measured on this split; the audit gate did not fail. No kill condition holds.

Section 7 (Jev): not run. It is moot until the local reranker clears section 6,
because Arm B is judged against Arm C on a test split.

## What I read in the two failures. None of this changes the verdict.

- **Regressions.** Under graded labels 23 queries got worse; counting only grade
  2, 8 did. Most of the regressions are reorderings among partially useful
  passages, and the audit found grade 1 to be the noisy label. That is an
  observation about the labels, not a reason to pass 6.3. Django (23.3%) and
  FastAPI (18.8%) carry the failure; Kubernetes (7.0%) and packaging (11.1%)
  are inside the limit.
- **Latency.** This is one run, on a machine that showed 2x run-to-run variance
  earlier the same day. It also ran with a 4-thread cap and one passage per
  call, where the dev figures quoted in 6.5 (207 to 255 ms p50) were default
  threads and sub-batches of 4. Django's long sections dominate the tail. A
  quiet-machine re-measurement is legitimate, since latency does not depend on
  labels, but it must be reported as a re-measurement beside this one and not
  in place of it. Even the best corpus here (Kubernetes, p95 581 ms) misses the
  p95 limit, so I do not expect a re-measure alone to pass.
- The dev split said RRF would regress on 8.4% of queries. The test split says
  14.9%. The dev estimate was optimistic, which is what a test split is for.

## What iterating means

1. On dev only: tune the fusion for fewer regressions (for example a rank floor
   that never moves the retrieval top 1 down by more than a set number of places,
   or a smaller k). Tune latency: pool of 15, a body cap below 6,000 characters
   before tokenizing, and the thread setting.
2. Amend the criteria with the new fixed settings, committed before step 3.
3. Build a NEW test split. Labeling this one used about 4.9M subagent tokens across 27 agents (summed from their usage reports).

## Not claimed

No claim about answer quality, tokens saved, or agent behaviour. The two-step
downstream evaluation has not been run. English only. One embedder behind the
baseline. One machine.
