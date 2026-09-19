# jdoc-rerank-bench

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
