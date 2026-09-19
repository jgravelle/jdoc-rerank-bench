# Sketch: `jdocmunch-mcp[rerank]`

Design sketch, 2026-09-19. Nothing here is built. It is written against
jdocmunch-mcp 1.142.0 (`121a5a2`). It lives in the harness repo because a new
large markdown file in the jdocmunch tree joins the replay corpus.

## What the user does

    pip install "jdocmunch-mcp[rerank]"
    set JDOCMUNCH_RERANK=local

No key. No account. Nothing leaves the machine after the one-time model
download. Without the env var, or without the extra, behaviour is unchanged.

## Packaging

    rerank = ["fastembed>=0.8.0"]

- Same dependency as the existing `fastembed` extra, on purpose. A user who
  installed offline embeddings already has the runtime. Measured venv: 138 MB,
  torch not loaded.
- Never a runtime dependency. The import is lazy and lives inside the provider.
- Model: `Xenova/ms-marco-MiniLM-L-6-v2`, file `onnx/model_quantized.onnx`
  (int8). Open question 1 below.

## Configuration

jdocmunch configures by env var (`config.py`), not by a config file. The PRD's
config-file table does not fit and is replaced by:

| Env var | Default | Meaning |
|---|---|---|
| `JDOCMUNCH_RERANK` | unset | `local`, `none`. Later: `jev`. Unset means `none`. |
| `JDOCMUNCH_RERANK_POOL` | 20 | Candidates fetched and reranked. Hard ceiling 30. |
| `JDOCMUNCH_RERANK_DEADLINE_MS` | 1500 | Whole stage. On expiry: original order. |
| `JDOCMUNCH_RERANK_REMOTE` | unset | `off` locks out every remote provider. |

The name is `rerank` everywhere. `semantic` already means embedding fusion in
`search_sections` and cannot be reused on 1.x.

## The seam

`tools/search_sections.py`, single-repo path.

1. **Over-fetch.** Line 227: `fetch_n = max_results * 5 if role else max_results`
   becomes `max(that, pool)` when a provider is active. Retrieval is otherwise
   untouched.
2. **Filters run as today** (tags, roles, byte length, level, dedupe) on the
   larger list.
3. **Snapshot the retrieval order.** Before reranking, keep `retrieval_top =
   results[:max_results]`.
4. **Rerank** between dedupe and the truncation at lines 346 to 362. Bodies come
   from `index._ensure_content(sec)`, which `attach_scores` already calls per
   row. Passage text is heading path (walk `parent_id`) plus body, 512-token cap.
   Length-sorted sub-batches of 4.
5. **Truncate** to `max_results`.

### The three `_score` consumers must not see the reranked order

- `attach_confidence` (line 454) reads the top-1 `_score` against a ceiling that
  depends on search mode.
- `build_verdict` turns that confidence into absence evidence.
- `record_ranking_event` (line 508) feeds top-1 and top-2 scores to the
  per-repo weight tuner.

After a rerank the first row no longer holds the highest `_score`. All three are
computed on `retrieval_top`. The reranker changes only the served order. This is
the defect class of the jdoc#106 follow-up, where confidence read 7x low and the
tuner walked to its floor.

Rows keep `_score` unchanged. They gain `_rerank_score` and `_retrieval_rank`.
Both are additive, and both are dropped by `compact` like other score fields.

### Interaction with existing paths

- `role=` and `profile=`: rerank first, then the role filter or the boost
  stable-sort, so the existing semantics hold within the new order.
- `semantic_only`, `lexical_engine`: no interaction. The reranker sees a list.
- `repo_group`: members run with reranking OFF. The fused list is reranked once,
  in the group path after RRF. One provider call per search.
- `min_answerability` / `min_quotability`: unchanged, applied after.

## Response

`_meta.rerank`, present only when a provider is configured:

    {"applied": true, "provider": "local", "model": "...", "pool": 20,
     "latency_ms": 212}
    {"applied": false, "reason": "timeout"}

Reasons: `timeout`, `provider_error`, `not_installed`, `model_unavailable`,
`remote_locked`, `bad_response`. With no provider configured the key is absent,
so an unconfigured install's responses do not change shape.

`semantic_debug` from the PRD is not needed: `_rerank_score` and
`_retrieval_rank` on each row are the diagnostics, and they carry no text.

Tool parameters: one, `rerank: bool | None`. `False` turns it off for a call.
`True` and `None` mean "as configured". No parameter can enable a provider,
pick one, or raise the pool (PRD MCP-004).

## Provider interface

`retrieval/rerank/` with `base.py`, `local.py`, `registry.py`:

    score(query, candidates, deadline) -> {id: float} | failure

Candidates are `{id, text, heading_path}` with harness-style opaque ids. Section
ids embed `doc_path`, so real ids never reach a remote provider. All-or-nothing:
a partial map is a failure (PRD REL-004). The harness's `bench/providers.py` is
the same shape, so an arm that wins there ports across directly.

## Failure behaviour

Every failure returns the retrieval order inside the normal time budget.

- Extra not installed and `JDOCMUNCH_RERANK=local`: `not_installed`, one log
  line at startup naming the pip command. Never an error to the client.
- Model not cached and the download fails: `model_unavailable`. The download is
  attempted once per process, outside the request path where possible (the
  existing warm-up hook for embedding providers is the model to copy, including
  its provider-aware cache probe: "cached for torch" is not "cached for ONNX").
- Deadline: checked between sub-batches. onnxruntime cannot be interrupted
  inside a batch, so the worst case overrun is one sub-batch of 4.

## Disclosure (required before release)

Standing suite rule since the PyPI quarantine: new network behaviour is in the
README before it ships.

- `local`: one model download from huggingface.co on first use, 23.1 MB for
  the int8 file (measured; fp32 is 91.0 MB), cached in the HF cache. No other network use.
- Any remote provider, later: query text and up to `POOL` passage bodies go to
  the named vendor. Its own README section, and `JDOCMUNCH_RERANK_REMOTE=off`.

## Tests the PR must carry

- Provider unset: responses equal the previous release's on a fixed query set
  after dropping volatile `_meta` keys (`latency_ms`, `tokens_saved`, totals).
  Byte-identical is not achievable and is not the claim.
- Provider unset: `fastembed` and `onnxruntime` never imported (assert on
  `sys.modules`).
- Confidence, verdict and the ranking event are identical with reranking on and
  off, using a fake provider that reverses the list.
- Each failure reason, with a fake provider.
- `rerank=True` with no provider configured does nothing.
- A second trivial provider added without touching `search_sections` (PRD AC-17).
- Fixture pins the embedding provider and the rerank env vars. "auto" reads the
  developer's site-packages and CI installs neither runtime.
- Replay gate: unchanged with the provider unset. A second replay run with
  `local` is informative only and is not a gate.

## Open questions

1. **int8 through fastembed is unmeasured.** The harness loaded
   `model_quantized.onnx` with onnxruntime directly. `TextCrossEncoder.
   add_custom_model` exists in 0.8.0 and takes a model file, but I have not run
   it. The alternative is onnxruntime + tokenizers + huggingface_hub directly,
   all of which the extra already installs. Measure both before choosing.
2. **Thread count.** onnxruntime defaults to all cores. Inside an MCP server
   beside an embedder that may be too greedy. Unmeasured.
3. **First-query cost.** Model load measured 174 ms warm. Cold download and
   first-inference warm-up are unmeasured.
4. **English only.** The ms-marco model is English. Behaviour on other languages
   and on code-heavy sections is unmeasured.
5. **Rank transform.** Set by `DECISION_CRITERIA.md`, not here.
