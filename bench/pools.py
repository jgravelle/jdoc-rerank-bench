"""Build and cache baseline candidate pools from an unmodified jdocmunch.

One pool file per (corpus, run). Each line is one query:
  {qid, class, query, rankings: {"A-lex": [ids], "A-hyb": [ids]},
   candidates: {id: {title, summary, heading_path, body, answerability}}}

Every later arm reads these files and never calls jdocmunch again, which is
what makes a run replayable (AC-04). Pools hold document text, so they live
under pools/ (gitignored) and are never published with the labels.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BODY_CHAR_CAP = 6000  # ~1,500 tokens (JEV-004); cut at a paragraph boundary

# Arm name -> search_sections kwargs. `semantic=None` is the shipped default.
BASELINES = {
    "A-lex": {"semantic": False},
    "A-hyb": {"semantic": None},
}
EXPECTED_MODE = {"A-lex": "lexical", "A-hyb": "hybrid"}


def cap_body(text: str, cap: int = BODY_CHAR_CAP) -> str:
    if len(text) <= cap:
        return text
    cut = text.rfind("\n\n", 0, cap)
    return text[: cut if cut > cap // 2 else cap]


def heading_path(index, sid: str) -> list[str]:
    """Titles from the document root down to this section."""
    out, seen = [], set()
    while sid and sid not in seen:
        seen.add(sid)
        sec = index.get_section(sid) or {}
        if sec.get("title"):
            out.append(sec["title"])
        sid = sec.get("parent_id")
    return out[::-1]


def jdoc_revision() -> str:
    """Source checkouts report __version__ 'unknown', so pin the commit."""
    import subprocess
    import jdocmunch_mcp
    src = Path(jdocmunch_mcp.__file__).parent
    try:
        return subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True,
                              text=True, encoding="utf-8", check=True).stdout.strip()
    except Exception:
        return "unknown"


def index_corpus(path: str, name: str, store: str, embeddings: bool) -> dict:
    from jdocmunch_mcp.tools.index_local import index_local

    out = index_local(
        path=path, name=name, storage_path=store,
        use_ai_summaries=False, use_embeddings=embeddings, incremental=False,
    )
    if not out.get("success"):
        raise RuntimeError(f"indexing failed: {out}")
    return out


def build_pools(repo: str, queries: list[dict], store: str, n: int, arms: list[str]) -> list[dict]:
    from jdocmunch_mcp.storage.doc_store import DocStore
    from jdocmunch_mcp.tools.search_sections import search_sections

    ds = DocStore(base_path=store)
    index = ds.load_index(*ds._resolve_repo(repo))
    if not index:
        raise RuntimeError(f"repo not indexed in {store}: {repo}")

    rows = []
    for q in queries:
        rankings, scores, cands = {}, {}, {}
        for arm in arms:
            out = search_sections(repo=repo, query=q["query"], max_results=n,
                                  storage_path=store, **BASELINES[arm])
            if "results" not in out:
                raise RuntimeError(f"{arm} failed on {q['qid']}: {out.get('error')}")
            # Control: with no embeddings or no provider, a hybrid request is
            # served lexically and would score as a second copy of A-lex.
            mode = out["_meta"].get("search_mode")
            if mode != EXPECTED_MODE[arm]:
                raise RuntimeError(f"{arm} ran as {mode!r} on {q['qid']}; "
                                   f"expected {EXPECTED_MODE[arm]!r}")
            rankings[arm] = [r["id"] for r in out["results"]]
            scores[arm] = [r.get("_score") for r in out["results"]]
            for r in out["results"]:
                if r["id"] in cands:
                    continue
                sec = index.get_section(r["id"]) or {}
                cands[r["id"]] = {
                    "title": r.get("title"),
                    "summary": r.get("summary"),
                    "heading_path": heading_path(index, r["id"]),
                    # doc_path is for the labeler only. It is a filesystem
                    # path and never goes to a provider (PRIV-003).
                    "doc_path": r.get("doc_path"),
                    "content_hash": r.get("content_hash"),
                    "answerability": r.get("_answerability"),
                    "body": cap_body(index._ensure_content(sec) if sec else ""),
                }
        rows.append({"qid": q["qid"], "class": q["class"], "query": q["query"],
                     "rankings": rankings, "scores": scores, "candidates": cands})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", required=True, help="path to the pinned corpus checkout")
    ap.add_argument("--name", required=True, help="corpus name; also the repo id")
    ap.add_argument("--snapshot", required=True, help="commit SHA or snapshot date (BENCH-001)")
    ap.add_argument("--queries", required=True, help="JSONL of {qid, class, query}")
    ap.add_argument("-n", type=int, default=20)
    ap.add_argument("--arms", default="A-lex,A-hyb")
    ap.add_argument("--store", default=str(ROOT / "store"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    arms = args.arms.split(",")
    # "auto" picks whichever embedder this box has installed, so an unpinned
    # A-hyb is a different arm on every machine and the header could not say which.
    if "A-hyb" in arms and not os.environ.get("JDOCMUNCH_EMBEDDING_PROVIDER"):
        ap.error("A-hyb needs JDOCMUNCH_EMBEDDING_PROVIDER set explicitly")
    queries = [json.loads(line) for line in Path(args.queries).read_text(encoding="utf-8").splitlines() if line.strip()]
    index_corpus(args.corpus, args.name, args.store, embeddings="A-hyb" in arms)
    rows = build_pools(f"local/{args.name}", queries, args.store, args.n, arms)

    import jdocmunch_mcp
    header = {
        "_run": {
            "corpus": args.name, "snapshot": args.snapshot, "n": args.n, "arms": arms,
            "jdocmunch_version": getattr(jdocmunch_mcp, "__version__", "unknown"),
            "jdocmunch_file": jdocmunch_mcp.__file__,
            "jdocmunch_commit": jdoc_revision(),
            "embedding_provider": os.environ.get("JDOCMUNCH_EMBEDDING_PROVIDER"),
            "date": _dt.datetime.now().isoformat(timespec="seconds"),
        }
    }
    out = Path(args.out or ROOT / "pools" / f"{args.name}.n{args.n}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in [header, *rows]:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{len(rows)} pools -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
