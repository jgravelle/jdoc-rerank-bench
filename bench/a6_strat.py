r"""Batch-3 stratified fetch. Frozen by `results/A6-sourcing-batch3.md` (`9549e08`).

Samples Q5 and Q4 candidates from Stack Exchange `/search/advanced` matching on
`title=`, because top-voted-by-tag cannot reach those floors.

⚠⚠ The phrase list selects CANDIDATES only. Every row is classified by the same
`a6_queries.classify` used for batches 1 and 2, and a row that misses the target
stratum is DROPPED, never relabelled. Q3's surplus may not be spent on Q4/Q5.

Nothing here reads retrieval, a reranker, or any Jev score.

    python -m bench.a6_strat --corpus django --tags django --prefix dj3 --want 30
"""

from __future__ import annotations

import argparse
import collections
import gzip
import html
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .a6_queries import ROOT, classify, jaccard, norm, spent, toks

ADV = "https://api.stackexchange.com/2.3/search/advanced"

# Frozen in results/A6-sourcing-batch3.md. Do not edit after that commit.
PHRASES_Q5 = ["both", "together", "combine", "integrate", "as well as",
              "while still", "at the same time", "separate"]
PHRASES_Q4 = ["best practice", "best way", "should i", "recommended", "proper way",
              "when to use", "convention", "vs", "difference between"]


def get(title: str, tag: str) -> tuple[list[dict], int | None]:
    q = urllib.parse.urlencode({"order": "desc", "sort": "votes", "title": title,
                                "tagged": tag, "site": "stackoverflow", "pagesize": "100"})
    req = urllib.request.Request(f"{ADV}?{q}", headers={
        "Accept-Encoding": "gzip", "User-Agent": "jdoc-rerank-bench/a6"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw, enc = r.read(), r.headers.get("Content-Encoding")
    except urllib.error.HTTPError as e:
        print(f"    ! HTTP {e.code} for title={title!r} tag={tag}", flush=True)
        return [], None
    if enc == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    d = json.loads(raw.decode("utf-8"))
    return d.get("items", []), d.get("quota_remaining")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--tags", required=True, help="comma-separated; each fetched separately (OR)")
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--want", default="Q5=9,Q4=4",
                    help="per-class caps, e.g. 'Q5=9,Q4=4'. Spread beats one corpus carrying a stratum.")
    a = ap.parse_args(argv)

    targets = {k: int(v) for k, v in (p.split("=") for p in a.want.split(","))}
    keep_classes = list(targets)
    sq, st = spent()
    print(f"spent: {len(sq)} qids, {len(st)} texts")

    # Candidate cache: the phrase lists are frozen, so the raw draw is too.
    # Re-running to widen a per-class cap must not re-spend API quota.
    cache = ROOT / "runs" / "a6-strat-cache" / f"{a.corpus}.json"
    if cache.exists():
        cand = json.loads(cache.read_text(encoding="utf-8"))
        print(f"{len(cand)} unique candidates for {a.corpus} (from cache, 0 requests)")
    else:
        seen, cand, quota = set(), [], None
        for tag in a.tags.split(","):
            for phrase in PHRASES_Q5 + PHRASES_Q4:
                items, q = get(phrase, tag)
                if q is not None:
                    quota = q
                new = 0
                for it in items:
                    if it["question_id"] in seen:
                        continue
                    seen.add(it["question_id"])
                    cand.append(it)
                    new += 1
                print(f"  {tag} title={phrase!r}: {len(items)} hits, {new} new (quota={quota})", flush=True)
                time.sleep(0.4)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(cand), encoding="utf-8")
        print(f"{len(cand)} unique candidates for {a.corpus} (cached)")

    # Highest-voted first, so the kept rows are still top-voted WITHIN the stratum.
    cand.sort(key=lambda it: -(it.get("score") or 0))
    kept, drop_qid, drop_dup, drop_class = [], 0, 0, collections.Counter()
    for want_class in keep_classes:
        for it in cand:
            if sum(k["class"] == want_class for k in kept) >= targets[want_class]:
                break
            qid = f"{a.prefix}{it['question_id']}"
            if qid in sq or any(k["qid"] == qid for k in kept):
                drop_qid += 1
                continue
            title = html.unescape(it["title"]).strip()
            cls = classify(title)
            if cls != want_class:
                drop_class[cls] += 1
                continue
            t = toks(norm(title))
            if any(jaccard(t, s) >= 0.85 for s in st):
                drop_dup += 1
                continue
            kept.append({"qid": qid, "class": cls, "query": title,
                         "source": f"stackoverflow.com/q/{it['question_id']}",
                         "so_score": it.get("score"), "so_tags": it.get("tags", []),
                         "sourced": "batch3-stratified"})

    dest = ROOT / f"queries/_draft/a6-batch3-{a.corpus}.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(json.dumps(r) for r in kept) + "\n", encoding="utf-8")
    print(f"wrote {len(kept)} -> {dest.name}")
    print(f"  dropped: {drop_qid} spent/dup-id, {drop_dup} near-dup text, "
          f"{sum(drop_class.values())} wrong stratum {dict(drop_class)}")
    print("  kept classes:", dict(sorted(collections.Counter(r["class"] for r in kept).items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
