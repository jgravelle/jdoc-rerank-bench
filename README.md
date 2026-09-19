# jdoc-rerank-bench

## Outcome, 2026-09-19: the local reranker does not ship

Decision by J. under `DECISION_CRITERIA.md` (`074dfa3` + A1 + A2): **do not ship.**
Check 6.3 (at most 12% of queries made worse) failed on two independent test
splits, 14.9% and 13.7%, and is not overridden. No third split will be run with
this approach.

- The gain was real on both splits: +0.097 [+0.066, +0.126] and +0.058 [+0.033, +0.084] nDCG@5.
- Latency was solved: 195 / 288 ms p50 / p95 for a pool of 15 on CPU.
- Jev (Arm B) was never run. Section 7 judges it against a local reranker that
  has cleared section 6, and none has.
- The largest effect measured here was jdocmunch's own hybrid search against
  lexical search: +0.09 to +0.18. The follow-on work is getting users onto that
  baseline.

Read, in order: `DECISION_CRITERIA.md`, `results/DECISION_MEMO-2026-09-19.md`,
`results/DECISION_MEMO-2-2026-09-19.md`. `docs/rerank-extra-sketch.md` and the A2
config are design notes for a negative result. They are not a plan.

Offline harness for the jDocMunch rerank POC. It lives outside the jdocmunch-mcp
tree on purpose: that repo's replay fixture indexes the whole repo, and its sdist
ships tracked files.

## Arms

| Arm | Order |
|---|---|
| A-lex | jdocmunch top-k, `semantic=False` |
| A-hyb | jdocmunch top-k, shipped default (BM25 + embeddings, RRF) |
| A' | pool reranked by jdocmunch's own `_answerability` |
| O | pool reranked by labels (ceiling) |
| B | pool reranked by Jev |
| C | pool reranked by a local cross-encoder |

## Build pools

Set `PYTHONPATH` to the jdocmunch-mcp `src` directory and this directory.
Set `JDOCMUNCH_EMBEDDING_PROVIDER` for A-hyb. The run stops if it is unset.

    python -m bench.pools --corpus <path> --name <corpus> --snapshot <sha> --queries queries/<corpus>.jsonl

Queries are JSONL: `{qid, class, query}`. Classes are Q1 to Q6.
Pools are written to `pools/`. They hold document text and are gitignored.

## Tests

    python -m pytest tests -q

## Not built yet

Arm scoring and reports, labels format, latency probe, Jev and cross-encoder
providers, the two-step downstream evaluation.
