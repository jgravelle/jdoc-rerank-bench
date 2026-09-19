# First-time `[fastembed]` setup cost, 2026-09-19

One machine (24-core Windows desktop, CPU only), jdocmunch-mcp `bfdac85`,
fastembed 0.8.x, Python 3.12, fresh venv, `uv pip install --no-cache`.
torch was never loaded. `use_ai_summaries=False`.

| Step | Cost |
|---|---|
| `pip install jdocmunch-mcp` (no package cache) | 10 s |
| adding `fastembed` | 44 s; venv 169 MB in total |
| first model download and load, `all-MiniLM-L6-v2` ONNX, empty cache | 27.3 s; 87 MB on disk |

| Corpus | Sections | Lexical index | Embedded index | Extra | Per 1,000 sections |
|---|---|---|---|---|---|
| Packaging guide | 989 | 1.0 s | 7.6 s | 6.6 s | 6.7 s |
| FastAPI | 5,207 | 2.4 s | 34.1 s | 31.7 s | 6.1 s |
| Django | 7,493 | 12.1 s | 63.9 s | 51.8 s | 6.9 s |
| Docker | 11,197 | 17.3 s | 101.1 s | 83.8 s | 7.5 s |
| Kubernetes | 15,697 | 49.1 s | 164.7 s | 115.6 s | 7.4 s |

All five embedded indexes loaded with `_has_embeddings() == True`. The five
embedded stores together take 438 MB.

A first attempt timed the embedded pass at under a second per corpus. Those
numbers were refusals, not indexing: jdocmunch returns `corpus_already_indexed`
when one source folder is indexed under a second name in the same store. The
table above is the re-run in a separate store.
