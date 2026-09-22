# jdoc-rerank-bench

## Outcome, 2026-09-19: the local reranker does not ship

Decision by J. under `DECISION_CRITERIA.md` (`074dfa3` + A1 + A2): **do not ship.**
Check 6.3 (at most 12% of queries made worse) failed on two independent test
splits, 14.9% and 13.7%, and is not overridden. No third split will be run with
this approach.

- The gain was real on both splits: +0.097 [+0.066, +0.126] and +0.058 [+0.033, +0.084] nDCG@5.
- Latency was solved: 195 / 288 ms p50 / p95 for a pool of 15 on CPU.
- Jev (Arm B) **was run once**, on 2026-09-20, as a pre-registered exploratory
  screen on the already-spent splits. **No figure from it is published here**
  (see "Arm B is withheld" below). Section 7 is unchanged and unmet: it judges
  Jev against a local reranker that has cleared section 6, and none has.
- The largest effect measured here was jdocmunch's own hybrid search against
  lexical search: +0.09 to +0.18. The follow-on work is getting users onto that
  baseline.

## Arm B is withheld, and the reason is the vendor's terms, not the result

Jev's exploratory screen ran on 2026-09-20. Its memo, its tuned threshold, its
per-arm deltas and its run driver are **held privately** and are not in this
repository, in any branch or any commit.

The hold is a terms question. The Master Customer Agreement fetched on
2026-09-20 carried no publish-benchmarks restriction, while indexed copies and
the older preview/evaluation terms still show one — and which agreement governs
this account has not been confirmed in writing. Publishing numbers under the
second would breach it, so nothing is published under either until the vendor
answers.

**Do not read this as a result in either direction.** Withheld is withheld. Two
caveats travel with those numbers whenever they are eventually quoted: the
hosted judge was graded against LLM-produced labels using near-rubric wording,
so part of its margin is grader agreement this harness cannot isolate, and it is
not deterministic where the local model is.

## A6: the confirmatory label set

This branch adds the A6 query splits, hybrid pools, 4,020 drafted labels and the
human-audit packs for the confirmatory study. It carries no Arm B material.

`results/LABEL-DESIGN-A6.md` is the design and `results/RUBRIC-A6-grade1.md` the
tightened grade-1 rubric. ⚠ Both were written on a local branch named
`exploratory-jev` and say so; that branch is not published, and the paths inside
them are the author's machine. They are reproduced **verbatim** rather than
tidied, because a pre-registration edited before publication is not a
pre-registration.

⚠ The labels are **drafts from a local model** (Ollama `gemma4:latest`, digest
pinned, temperature 0) and are **not evidence yet**. They become evidence only
when the human audit in `results/A6-audit-pack.md` clears the gates in
`LABEL-DESIGN-A6.md` section 7. The audit has not been run.

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

## Jev (Arm B): not evaluated

Nothing in this repository is a measurement of Jev. There is no Jev provider in
`bench/providers.py`, no Jev score in `results/`, and no call was made to the
service. `DECISION_CRITERIA.md` section 7 sets what arm B would have to show:
B minus C with its lower bound above zero and a point estimate of at least
+0.04, or B within ±0.02 of C with live p95 at or below C's; in both cases live
p95 at most 1,000 ms, and vendor terms that permit publishing the comparison.
That section applies only after a local reranker passes section 6.

## Not built

The Jev provider, and the two-step downstream evaluation (rows, then the
agent's `get_section` calls) that the default-on decision needs.

## Attribution and what is not here

The files in `queries/` are lightly cleaned titles of Stack Overflow questions
(and, for the FastAPI dev split, FastAPI GitHub Discussions). Stack Overflow
content is licensed CC BY-SA; each row's `source` field links the original
question, and the cleaned queries are shared under the same licence.

The corpora are the public documentation of Kubernetes, FastAPI, Django, the
Python Packaging User Guide and Docker, pinned by the commit SHAs recorded in the
memos. Their text is not redistributed here: `pools/`, `label_tasks/` and
`audit/` hold passage text and are gitignored. `pools-test*.sha256` lets anyone
who rebuilds the pools check that they match the frozen ones.
