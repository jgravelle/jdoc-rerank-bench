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
