# A6 corpora — snapshots and indexes

**2026-09-20.** Four corpora per `LABEL-DESIGN-A6.md` §1. No pools, no labels, no
Jev calls at the time of writing.

| Slot | Corpus id | Role | Indexed path | Snapshot SHA |
|---|---|---|---|---|
| C1 | `packaging` | policy-style | `corpora/packaging-src/source` | `457e74f03e630c7d4414bb39e8e77d4b61df6ee9` (2026-09-09) |
| C2 | `fastapi` | framework docs | `corpora/fastapi-src/docs/en/docs` | `50113da16fec53b66b80d75e80a89296de4fa5a5` (2026-09-01) |
| C3 | `django` | large RST docs | `corpora/django-rst` | ⚠ see below |
| C4 | `pytest` | **NEW vs A3 spent** | `corpora/pytest-src/doc/en` | `6a0de9be56365e75ff30d75cee9654739ca95f97` (2026-09-18) |

`pytest` was cloned and indexed on 2026-09-20 (`git clone --depth 1` of
`github.com/pytest-dev/pytest`, so the SHA above is the snapshot and the clone
carries no earlier history).

⚠ **`corpora/django-rst` is not a git checkout**, so it carries no SHA of its
own. The A3 memos recorded django at `935edaa91b756325352ca70d5eba49a64b70d28c`
(from `runs/build_test2_pools.sh`) and that directory has not been rebuilt since,
but **this is provenance by inheritance, not a verified snapshot.** If django is
kept as C3 for the ship call, re-clone it into a git checkout and record the SHA
before the pool freeze, or state the limitation in the confirmatory memo. The
honest minimum in `LABEL-DESIGN-A6.md` §1 (packaging + fastapi + pytest) avoids
the question entirely.

## Index state in `store/` (all with embeddings)

Indexed with `JDOCMUNCH_EMBEDDING_PROVIDER=sentence-transformers`, matching the
prior freezes. A6 §4.1 forbids retuning retrieval, so the embedder is not changed.

| Index | Sections | Embeddings sidecar |
|---|---|---|
| `local/packaging` | 989 | yes |
| `local/fastapi` | 5,207 | yes |
| `local/django` | 7,493 | yes |
| `local/pytest` | **2,170** (276 docs) | yes, 15.6 MB |

`docker` and `k8s` remain indexed from A3 and are **not** A6 corpora.
`LABEL-DESIGN-A6.md` §1 explicitly declines docker.

⚠ The pytest index took 19 s including embeddings. Nothing about it is frozen yet:
freezing happens at the pool-hash step (`pools-a6.sha256`), which has not run.

## A6 pools (§9 steps 8-9, 2026-09-20)

Built by `runs/build_a6_pools.sh`, settings COPIED from
`runs/build_test2_pools.sh`: `JDOCMUNCH_EMBEDDING_PROVIDER=sentence-transformers`,
n=20, arms `A-lex,A-hyb`, `--reuse-index`. §4.1 forbids retuning retrieval for A6
and nothing here was retuned.

| Pool file | Queries | Index | Snapshot |
|---|---|---|---|
| `pools/packaging-a6dev.n20.jsonl` | 21 | `local/packaging` | `457e74f0…` |
| `pools/pytest-a6dev.n20.jsonl` | 42 | `local/pytest` | `6a0de9be…` |
| `pools/fastapi-a6dev.n20.jsonl` | 12 | `local/fastapi` | `50113da1…` |
| `pools/django-a6dev.n20.jsonl` | 5 | `local/django-a6` | `446d9cf6…` |
| `pools/packaging-a6test.n20.jsonl` | 56 | `local/packaging` | `457e74f0…` |
| `pools/pytest-a6test.n20.jsonl` | 47 | `local/pytest` | `6a0de9be…` |
| `pools/fastapi-a6test.n20.jsonl` | 46 | `local/fastapi` | `50113da1…` |
| `pools/django-a6test.n20.jsonl` | 39 | `local/django-a6` | `446d9cf6…` |

268 queries, 80 dev + 188 test, matching the frozen query files row for row.

**Manifest: `pools-a6.sha256`, 8 files, `sha256sum -c` all OK.** ⚠ The pool files
themselves are NOT committed — `.gitignore:3` is `pools/`, because pools carry
document text (PRIV: they are never published with the labels). The manifest is
the committed artifact and is what makes the pools immutable from here.

### Provenance checks that passed

- **Every arm ran as itself.** `build_pools` raises when an arm's
  `_meta.search_mode` is not the expected one, so a missing embedding sidecar
  cannot be written as A-hyb after silently degrading to lexical.
- **A-hyb differs from A-lex on all 268 queries.** That is the second, independent
  check on the same thing: identical rankings everywhere would mean the embedding
  channel contributed nothing.
- **Judgment depth is covered.** Every query carries 20 A-hyb candidates, so
  §4.3's `rankings["A-hyb"][:15]` is never short.
- **qid order and class agree with the query files** for all eight pairs.

⚠ **jdocmunch commit `66beb09`, where the prior freezes used
`121a5a23749feb36efd6693c1ed6efff42dacdad`.** The only change in that range
touching retrieval is a `_meta.tip` string on the lexical-no-embeddings path
(`git diff 121a5a2..HEAD -- src/jdocmunch_mcp/tools/search_sections.py`: 7
insertions, 1 deletion). Ranking and scoring are byte-identical, so A-hyb is the
same arm; each pool header records the commit regardless.

## A6 label tasks exported (§9 step 10, first half, 2026-09-20)

§9 step 2 was still unticked and `bench/labeling.py` still carried the old
grade-1 one-liner, so it was done first: `GUIDELINES_A6` is the tightened rubric
from `results/RUBRIC-A6-grade1.md`. ⚠ `GUIDELINES` is **not** edited in place —
A3's exports and labels were produced under it and a study's rubric is part of
its record. Grades 0 and 2 are carried over verbatim; rewriting grade 2 toward
Jev's `true` criterion is the shared-method bias A3 flagged.

`export` gained `--arm` and `--depth`. ⚠⚠ Without them it exports **every**
candidate, i.e. the union of both arms' top-20, which measures **23–35 per query
here, not 20**. §4.3 freezes the judgment list as `rankings["A-hyb"][:15]`, so A6
exports `--arm A-hyb --depth 15`: **4,020 pairs instead of ~7,700**, and no
A-lex-only candidate is put in front of a labeler for a study whose baseline is
A-hyb.

| Task dir | Tasks | Pairs |
|---|---|---|
| `label_tasks/packaging-a6dev/` | 21 | 315 |
| `label_tasks/pytest-a6dev/` | 42 | 630 |
| `label_tasks/fastapi-a6dev/` | 12 | 180 |
| `label_tasks/django-a6dev/` | 5 | 75 |
| `label_tasks/packaging-a6test/` | 56 | 840 |
| `label_tasks/pytest-a6test/` | 47 | 705 |
| `label_tasks/fastapi-a6test/` | 46 | 690 |
| `label_tasks/django-a6test/` | 39 | 585 |
| **total** | **268** | **4,020** |

6.25 MiB of prompt text, about 1.64M input tokens with one call per query.

Smoke-tested before use: depth 15 equals A-hyb's top 15 as a set; the keyed set
is shuffled per qid so `c01` is not the top-ranked passage (0 of 5 on the dev
django tasks); the A6 grade-1 text reaches the task file and the old
"partially useful" line does not; grade 2 is byte-identical; no arm name, rank or
section id leaks into a blind task; and the default path still exports the full
union under the old rubric.

⚠ `label_tasks/` is gitignored (`.gitignore:7`) because tasks carry document
text, so the exported tasks are machine-local and only the labels they produce
get committed.

⚠ Same applies to `runs/`, so **`runs/build_a6_pools.sh` is NOT in the
repository** — matching `build_test2_pools.sh`, which is also ignored. The pool
build settings are recorded in the section above so the procedure survives the
script; a reader cannot run it from a fresh clone.

**Drafting is NOT started.** §12 item 4 (the draft-label provider/model pin) is
still an open decision for J.

## A6 draft labelling — pipeline proven, throughput blocked (2026-09-20)

`bench/a6_draft.py`. Pinned model, `temperature=0`, `seed=0`,
`response_format=json_object`, grades in `<qid>.labels.json` (exactly the keymap
keys, which is what `collect` accepts) and one short note per passage in a
`<qid>.notes.json` sidecar.

⚠ A missing or out-of-range grade **raises**; it is not defaulted to 0. A silent 0
is indistinguishable from a judged 0 and would bias every metric downward on
precisely the passages the grader found hardest.

### Route 1, `ollama` — PREFERRED, unreachable as configured

The Mac Mini answers over Tailscale at 2–6 ms, so this is not a network problem:

- Ollama's own port **11434 is closed**. Ollama binds `127.0.0.1` by default, so
  it is not listening on the Tailscale interface.
- Open WebUI **0.8.8** on `:8080` fronts it, and `/api/config` reports
  `"auth": true` with **`"enable_api_keys": false`** — so `/ollama/api/tags`,
  `/api/models` and `/openai/models` all answer `401 Not authenticated` and there
  is no programmatic route in.

Either fix unblocks it: `launchctl setenv OLLAMA_HOST 0.0.0.0` plus an Ollama
restart, or switch API keys on in Open WebUI. ⚠ No Gemma tag could be confirmed,
because listing models needs the auth that is unavailable.

### Route 2, `openai` gpt-4o-mini — no credits

`gpt-4o-mini-2024-07-18` returns HTTP 429 `credit_balance_exhausted`. Priced from
developers.openai.com/api/docs/pricing on 2026-09-20 at **$0.15 / $0.60 per
Mtok**, the full pass would be **≈ $0.34** (1.64M in, ~150k out).

⚠ Fixed on the way past: a 429 was being retried five times with backoff, and
`insufficient_quota` arrives as a 429 that no backoff can fix. Terminal 429s now
fail fast.

### Route 3, `groq` openai/gpt-oss-120b — works, throttled

The pipeline is **proven end to end on this route**. One smoke task
(`dj321939490`, "Unique together constraint including specific field value")
graded 13 × 0, 1 × 1, 1 × 2, and the placement is right: **2** to
`UniqueConstraint.condition` (the citable answer), **1** to the `UniqueConstraint`
parent page (necessary, names `condition`, incomplete), **0** to the adjacent
`fields` / `expressions` / `unique_together` attributes — the tightened rubric
applied correctly, including its prefer-0 tiebreak.

Then the free tier bites. Measured from the response headers: **8,000 TPM** on
`gpt-oss-120b`, `gpt-oss-20b` and `qwen3.8-27b` alike (1,000 requests/day).
Against the exported tasks:

| | |
|---|---|
| tasks | 268 |
| median task | 5,777 tokens |
| p90 | 8,580 |
| max | 12,408 |
| **tasks that cannot fit one 8,000-TPM minute** | **79 (29%)** |
| total | ~1.64M input tokens → **≥3.4 h** at 8,000 TPM |

⚠ Also found here: Groq is behind Cloudflare, which answers urllib's default
`Python-urllib/3.x` with **HTTP 403 code 1010**, a browser-signature block. The
same request through curl passed, which is how the User-Agent was isolated.

So Groq needs the 15-passage task split into chunks to fit the cap. **That is a
change to the grading unit and is not being made unasked** — it repeats the rubric
per chunk and removes cross-passage context, which is a deviation the memo would
have to carry.

**Drafting is NOT complete: 1 of 268 tasks drafted.** The rubric, the export, the
blind-task shape and the grading pipeline are all verified; only throughput is
unresolved.
