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
