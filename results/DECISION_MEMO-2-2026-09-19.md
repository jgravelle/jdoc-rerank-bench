# Decision memo 2 — jDocMunch local reranker, test split 2

Date: 2026-09-19. Criteria: `DECISION_CRITERIA.md` at `074dfa3` with amendments
A1 (`97ff17e`) and A2 (`d03ae89`). Both amendments are post hoc to the original
criteria and both were committed before this split existed.

## Verdict: ITERATE, for the second time, on the same check

Four of five ship checks pass. 6.3 (regressions) fails again: 13.7% against a
12% limit. No kill condition is met. This split is now spent too.

## Order of events, from the harness history

| Commit | What |
|---|---|
| `d03ae89` | Amendment A2: fixed settings, latency rule, new-split rules |
| `cf6dad9` | Test split 2 queries and sha256 of the five pool files |
| `8243724` | Labels frozen (6,224 pairs) and the evaluator `bench/decide2.py`. Pool hashes re-verified first. |
| after that | One scoring pass of three runs. CPU load sampled just before: mean 5.4%, max 9.1%. |

## Setup

- 200 ranking queries and 20 out-of-corpus controls. Stack Overflow questions,
  none used in any earlier split. Five corpora: Kubernetes, FastAPI, Django,
  Python Packaging User Guide, and Docker (new, `docker/docs` at `7d6c8bf`).
  Decision set Q3 to Q5: 183 queries (79 / 51 / 53).
- **Selection disclosure.** Queries were chosen from titles alone, in vote order,
  by one agent per corpus that read no documentation. To reach the class minimums
  the agents walked further down their lists for Q4 and Q5 questions, and the
  Kubernetes and Django agents passed over a few Q3 titles to hold the total at
  40. That is selection by class. No reranker output existed.
- **Docker corpus caveat.** Docker's CLI and Dockerfile reference pages are
  generated from YAML and are not in the markdown tree that was indexed.
- Config under test, fixed by A2: int8 MiniLM-L-6, 512 tokens, one passage per
  call, 4 threads, hybrid top 15, gated promotion at 0.95, RRF k=10 among the
  promoted. torch not loaded.
- Labels: blind LLM grades. The audit of this labeling method was done by an
  independent second model, not a human (A1). This split's labels were not
  separately audited.
- Labeling used about 5.4M subagent tokens across 30 agents (summed from their
  usage reports).

## Results, nDCG@5, paired delta against the hybrid baseline

| Group | n | Baseline | Oracle gain, pool 15 | Delta [95% CI] | Better | Worse | Worse % |
|---|---|---|---|---|---|---|---|
| Q3 (fuzzy) | 79 | 0.444 | +0.429 | +0.087 [+0.043, +0.134] | 34 | 12 | 15.2% |
| Q4 (policy) | 51 | 0.538 | +0.308 | +0.005 [-0.027, +0.038] | 10 | 10 | 19.6% |
| Q5 (multi-concept) | 53 | 0.279 | +0.512 | +0.065 [+0.024, +0.110] | 15 | 3 | 5.7% |
| Q2, not decided on | 17 | 0.316 | +0.389 | +0.045 [-0.016, +0.128] | 2 | 3 | 17.6% |
| Kubernetes | 37 | 0.409 | +0.442 | +0.067 [+0.021, +0.118] | 15 | 5 | 13.5% |
| FastAPI | 37 | 0.395 | +0.456 | +0.042 [+0.007, +0.078] | 10 | 3 | 8.1% |
| Packaging | 38 | 0.383 | +0.404 | +0.104 [+0.035, +0.185] | 15 | 3 | 7.9% |
| Django | 36 | 0.424 | +0.504 | +0.068 [+0.006, +0.135] | 9 | 5 | 13.9% |
| Docker | 35 | 0.507 | +0.286 | +0.005 [-0.043, +0.052] | 10 | 9 | 25.7% |
| **Q3 to Q5 pooled** | 183 | 0.423 | +0.419 | **+0.058 [+0.033, +0.084]** | 59 | 25 | **13.7%** |

Sensitivity, only grade 2 counts as relevant: pooled +0.041 [+0.016, +0.067],
38 better, 16 worse (8.7%). Under that reading every per-corpus interval
includes zero, and Q4 is -0.007 [-0.041, +0.027].

Latency, pool of 15, three runs over all 220 queries: 198 / 310, 188 / 271,
195 / 288 ms (p50 / p95). Judged run, median p95: **195 / 288 ms**.

Out-of-corpus controls: median top score 0.346 on the 20 controls against 0.983
on answerable queries. The gate promoted nothing on 16 of 20 controls, and
nothing on 69 of 200 answerable queries.

## Section 6, quoted and applied

> 1. Pooled delta: lower bound of the interval above zero, and point estimate at
>    least **+0.04**

**PASS.** +0.058, lower bound +0.033.

> 2. Every corpus: point estimate above zero. No corpus with an interval entirely
>    below zero.

**PASS**, narrowly. Docker's point estimate is +0.005.

> 3. Regressions: at most **12%** of queries have a lower nDCG@5 than baseline.

**FAIL.** 25 of 183, 13.7%.

> 4. No query class in Q3 to Q5 with an interval entirely below zero.

**PASS.** Q4's interval is [-0.027, +0.038]: it includes zero and is not
entirely below it. Q4 shows no gain on this split.

> 5. Latency: p95 at most **500 ms**, p50 at most **300 ms**

**PASS.** 195 / 288 ms on the judged run, and all three runs pass.

## What A2 required this memo to state

- **Selection optimism, realised.** Tuning predicted 7.9% of queries worse
  (9.7% on the spent split alone) and a gain of +0.063 to +0.067. This split
  measured 13.7% and +0.058. The regression estimate was optimistic by about
  five points, which is the difference between passing and failing.
- **Per-corpus regressions.** Docker 25.7%, Django 13.9%, Kubernetes 13.5% are
  above 12%. FastAPI 8.1% and packaging 7.9% are under it. On the first test
  split the high corpora were Django and FastAPI. Which corpus regresses is not
  stable; that some corpus does is.

## What two test splits now say

| | Split 1 (RRF k=60, pool 20) | Split 2 (gated, pool 15) |
|---|---|---|
| Pooled gain | +0.097 [+0.066, +0.126] | +0.058 [+0.033, +0.084] |
| Queries worse | 14.9% | 13.7% |
| Queries worse, grade 2 only | 5.2% | 8.7% |
| Latency p50 / p95 | 398 / 1,251 ms (busy machine) | 195 / 288 ms |

- The gain is real on both splits. The gated transform gave up about 40% of it
  and bought back about one point of regressions, not the five the tuning
  predicted.
- Roughly one query in seven gets a lower graded nDCG@5 with this reranker,
  under two different transforms, on nine corpus-splits. I read that as a
  property of reranking with this model over these labels, not as something
  another round of transform tuning will remove. That is my reading, not a
  finding the criteria make.
- Where there is little headroom the reranker adds churn and no gain: Docker
  (baseline 0.507, oracle gain +0.286) and Q4 (baseline 0.538, +0.308) changed
  the top 5 often and gained nothing.
- The gate behaves sensibly on out-of-corpus questions: it left 16 of 20
  untouched. That is the first evidence in this project that "nothing relevant"
  may be detectable. It was not a pre-registered question.
- Latency is solved: pool of 15, 4 threads, one passage per call.

## Sections 8 and 9 applied

> - Gain is real but section 6.3 fails: tune the fusion on dev, then a NEW test
>   split. The spent one cannot be reused.

This applies again. No kill condition holds: the pooled lower bound is above
zero, latency passes, and the audit gate has not failed.

Section 7 (Jev): not run. The local reranker has not cleared section 6.

## Not claimed

No claim about answer quality, tokens saved or agent behaviour. The two-step
downstream evaluation has not been run. English only. One embedder behind the
baseline. One machine. LLM labels with a second-model audit.
