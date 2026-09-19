"""Dev-only tuning of the rank transform, pool depth and token cap.

Reads cached int8 one-passage-per-call scores (independent of pool by
construction, so a pool of 15 is the first 15 of the cached 20).
`--score` builds those caches; without it, prints the grid.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from .labeling import load_pools
from .metrics import bootstrap_ci, ndcg_at_k
from .providers import passage_text

ROOT = Path(__file__).resolve().parent.parent
K, BASE, DECIDE = 5, "A-hyb", ("Q3", "Q4", "Q5")


def fuse(pool, scores, k, floor):
    """RRF of retrieval rank and rerank rank. floor=f: the retrieval top 1
    never ends below position f (1-based); 0 disables."""
    sem = {s: r for r, s in enumerate(sorted(pool, key=lambda s: -scores[s]))}
    fused = {s: 1 / (k + r + 1) + 1 / (k + sem[s] + 1) for r, s in enumerate(pool)}
    order = [s for _, s in sorted(enumerate(pool), key=lambda t: (-fused[t[1]], t[0]))]
    if floor and order.index(pool[0]) > floor - 1:
        order.remove(pool[0])
        order.insert(floor - 1, pool[0])
    return order


def cache_path(corpus, tokens):
    return ROOT / "runs" / "scores" / f"{corpus}.tune-int8-b1-t{tokens}.json"


def do_score(corpora, tokens):
    from .levers import Ort
    m = Ort("int8", tokens)
    m.bucket = 1
    for c in corpora:
        out = {}
        for row in load_pools(ROOT / "pools" / f"{c}.n20.jsonl"):
            ids = row["rankings"][BASE]
            out[row["qid"]] = dict(zip(ids, m.score(row["query"], [passage_text(row["candidates"][i]) for i in ids])))
        cache_path(c, tokens).write_text(json.dumps(out), encoding="utf-8")
        print(c, tokens, len(out), flush=True)


def rows_for(corpora, tokens):
    rows = []
    for c in corpora:
        labels = defaultdict(dict)
        for line in (ROOT / "labels" / f"{c}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            labels[r["qid"]][r["section_id"]] = r["grade"]
        sc = json.loads(cache_path(c, tokens).read_text(encoding="utf-8"))
        for row in load_pools(ROOT / "pools" / f"{c}.n20.jsonl"):
            if row["class"] in DECIDE:
                rows.append((c, row["rankings"][BASE], sc[row["qid"]], labels[row["qid"]]))
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="dev=fastapi,k8s;spent=k8s-test,fastapi-test,packaging-test,django-test")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--tokens", default="512,384")
    a = ap.parse_args(argv)
    sets = {s.split("=")[0]: s.split("=")[1].split(",") for s in a.sets.split(";")}
    tokens = [int(t) for t in a.tokens.split(",")]
    if a.score:
        for t in tokens:
            do_score([c for cs in sets.values() for c in cs], t)
        return 0

    data = {(name, t): rows_for(cs, t) for name, cs in sets.items() for t in tokens}
    head = " | ".join(f"{n} delta [95% CI] | {n} worse %" for n in sets)
    print(f"| tokens | pool | k | floor | {head} | worst corpus worse % |")
    print("|---|---|---|---|" + "---|---|" * len(sets) + "---|")
    for t in tokens:
        for pool in (20, 15):
            for k in (60, 20, 10, 5, 2):
                for floor in (0, 3, 2):
                    cells, worst = [], 0.0
                    for name in sets:
                        per_c = defaultdict(list)
                        for c, base, sc, lab in data[(name, t)]:
                            b = ndcg_at_k(base, lab, K)
                            per_c[c].append(ndcg_at_k(fuse(base[:pool], sc, k, floor), lab, K) - b)
                        d = [x for v in per_c.values() for x in v]
                        ci = bootstrap_ci(d, iters=2000, seed=0)
                        cells += [f"{ci[0]:+.3f} [{ci[1]:+.3f}, {ci[2]:+.3f}]", f"{sum(x < -1e-9 for x in d) / len(d):.1%}"]
                        worst = max(worst, max(sum(x < -1e-9 for x in v) / len(v) for v in per_c.values()))
                    print(f"| {t} | {pool} | {k} | {floor or '-'} | " + " | ".join(cells) + f" | {worst:.1%} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())


def promote(pool, scores, tau, k=10):
    """Gated transform: passages whose sigmoid score is at least tau move to the
    front, ordered among themselves by RRF(k); everything else keeps its
    retrieval order. With nothing above tau the retrieval order is unchanged."""
    import math
    hi = [s for s in pool if 1 / (1 + math.exp(-scores[s])) >= tau]
    if not hi:
        return list(pool)
    keep = set(hi)
    return fuse(hi, scores, k, 0) + [s for s in pool if s not in keep]
