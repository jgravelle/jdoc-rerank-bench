# Decision criteria — jDocMunch rerank POC

**Status: IN FORCE as of 2026-09-19 (committed by J. / Grok Bot on J.'s instruction).**
This file is the pre-registration. It precedes any reranker score on the test
split (PRD DEC-003, AC-03). Thresholds below are locked; post-commit changes
must be labeled post hoc in the memo.

## 1. What is already spent

The FastAPI and Kubernetes studies of 2026-09-19 are the **dev split**. The
local reranker has been scored on all 107 of their ranking queries, and its
configuration (int8, 512 tokens, pool of 20) was chosen on them. Those results
cannot decide anything. They set the noise floor and nothing else.

Dev split, nDCG@5, reranking the hybrid top-20:

| | FastAPI (n=48) | Kubernetes (n=59) |
|---|---|---|
| Hybrid baseline | 0.279 | 0.391 |
| Oracle gain | +0.458 | +0.568 |
| 95% CI half-width of a paired delta | about 0.085 | about 0.085 |
| Local reranker, full re-sort | +0.108 [+0.026, +0.194] | +0.181 [+0.096, +0.263] |
| Local reranker, RRF fusion | +0.048 [+0.007, +0.092] | +0.099 [+0.053, +0.144] |
| Queries made worse, re-sort / RRF | 9 / 5 | 12 / 4 |

## 2. The test split

- New queries only. No query from the dev split, and no query written or
  selected after looking at any reranker output.
- At least **150** ranking queries, at least 30 in each of Q3, Q4 and Q5, plus
  about 20 Q6 controls. With 59 queries the half-width was 0.085; 150 should bring
  it near 0.055. That figure is an estimate, not a measurement.
- At least three corpora, at least one of which is not in the dev split, and at
  least one policy-style document set.
- Pools are built and labels are collected and frozen **before** any reranker
  scores them. The order is visible in the harness commit history.
- Labels are blind LLM grades. The human audit in section 3 applies to them.

## 3. Label audit gate (applies before anything else)

From `python -m bench.audit agree`, per stratum:

- LLM grade 0: human agrees it is 0 in at least **90%** of sampled items.
- LLM grade 2: human grades it 1 or 2 in at least **80%**.
- If either fails, the labels are not evidence. Fix the guidelines, relabel, and
  re-audit before any decision. The dev numbers above are then also void.

## 4. Primary metric and fixed settings

- Primary: paired delta in nDCG@5 against the hybrid baseline (`A-hyb`), over
  Q3 to Q5 pooled, with a 95% bootstrap interval over queries (5,000 resamples,
  seed 0). Q2 is reported and not decided on. Q6 is excluded.
- Fixed before the run: pool of 20, the rank transform (section 5), the model
  file, 512-token cap, the embedder behind `A-hyb`.
- Latency is measured on CPU on J.'s machine, torch not loaded, p50 and p95 of
  the whole rerank stage for one pool.

## 5. Rank transform (locked on dev)

Full re-sort made 21 of 107 dev queries worse (19.6%). RRF fusion made 9 worse
(8.4%). Under the regression limit in 6.3, re-sort fails on dev and RRF passes.

**The candidate is RRF fusion (k=60).** No weighted fusion for v1. After this
commit the transform does not change.

## 6. Ship the local reranker as an opt-in extra — all of

1. Pooled delta: lower bound of the interval above zero, and point estimate at
   least **+0.04** (dev RRF: +0.048 and +0.099).
2. Every corpus: point estimate above zero. No corpus with an interval entirely
   below zero.
3. Regressions: at most **12%** of queries have a lower nDCG@5 than baseline.
4. No query class in Q3 to Q5 with an interval entirely below zero.
5. Latency: p95 at most **500 ms**, p50 at most **300 ms** (dev: 207 to 255
   ms p50, 269 to 469 ms p95).
6. Out-of-corpus controls: the top reranked score on Q6 queries is reported. No
   threshold. It decides only whether a later "nothing relevant" signal is
   worth studying.

**Default-on is a separate, later decision.** It needs regressions at most
**6%**, p95 at most **250 ms**, and the two-step downstream evaluation
(rows, then the agent's `get_section` calls) showing fewer bodies fetched per
correct answer. Until then the extra is opt-in.

## 7. Jev (Arm B) — built as a provider only if

Arm B runs on the same frozen test pools, pinned model ID, schema version
recorded, scored twice with the cache off.

1. B minus C, paired: lower bound above zero and point at least **+0.04**; or
2. B within **±0.02** of C **and** live p95 latency at or below C's.

And in both cases: live p95 at most **1,000 ms** from J.'s connection, and
the vendor's terms permit publishing the comparison.

If neither holds, Jev is not integrated. The provider interface ships with the
local reranker alone. That outcome is a result, and it is published.

## 8. Iterate

- Gain is real but section 6.3 fails: tune the fusion on dev, then a NEW test
  split. The spent one cannot be reused.
- Gain is real but 6.5 fails: pool of 15, then re-test.
- Intervals are too wide to decide either way: say "inconclusive", add queries.

## 9. Kill

- Pooled lower bound at or below zero on the test split.
- Latency over the limit at every pool size from 10 to 20.
- The audit gate fails twice.

## 10. Reporting

The memo quotes this file verbatim from its committed revision and applies it
without amendment. Any change after the commit is labeled post hoc in the memo.
Per-class tables come first. The pooled figure is not the headline.
