"""Per-class report over cached pools, labels and provider scores.

Arms are derived here from cache, so rerunning reproduces every number.
Q6 (corpus cannot answer) is excluded from ranking metrics by design.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from .labeling import load_pools
from .metrics import bootstrap_ci, mrr, ndcg_at_k, oracle_order, precision_at_k

ROOT = Path(__file__).resolve().parent.parent


def rerank(pool: list[str], scores: dict[str, float]) -> list[str]:
    return [s for _, s in sorted(enumerate(pool), key=lambda t: (-scores.get(t[1], 0.0), t[0]))]


def rrf(pool: list[str], scores: dict[str, float], k: int = 60) -> list[str]:
    sem = {s: r for r, s in enumerate(rerank(pool, scores))}
    fused = {s: 1 / (k + r + 1) + 1 / (k + sem[s] + 1) for r, s in enumerate(pool)}
    return rerank(pool, fused)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pools", required=True)
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--base", default="A-hyb", help="the pool every reranker reorders")
    ap.add_argument("--depth", type=int, default=None, help="rerank only the top DEPTH of the pool")
    ap.add_argument("--only", default=None, help="print one group, e.g. ALL")
    args = ap.parse_args(argv)

    pool_file = Path(args.pools)
    corpus = pool_file.name.split(".")[0]
    labels: dict[str, dict[str, int]] = defaultdict(dict)
    for line in (ROOT / "labels" / f"{corpus}.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        labels[r["qid"]][r["section_id"]] = r["grade"]
    provs = {p.name.split(".")[1]: json.loads(p.read_text(encoding="utf-8"))["queries"]
             for p in sorted((ROOT / "runs" / "scores").glob(f"{corpus}.*.json"))}

    per_q: dict[str, dict[str, dict[str, float]]] = {}
    classes: dict[str, str] = {}
    for row in load_pools(pool_file):
        if row["class"] == "Q6":
            continue
        lab, base = labels[row["qid"]], row["rankings"][args.base][: args.depth]
        orders = dict(row["rankings"])
        orders["O"] = oracle_order(base, lab)
        for name, q in provs.items():
            orders[name] = rerank(base, q[row["qid"]]["scores"])
            orders[name + "+rrf"] = rrf(base, q[row["qid"]]["scores"])
        classes[row["qid"]] = row["class"]
        per_q[row["qid"]] = {a: {"ndcg": ndcg_at_k(o, lab, args.k), "p1": precision_at_k(o, lab, 1, min_grade=2),
                                 "mrr": mrr(o, lab, args.k, min_grade=2), "top": tuple(o[: args.k])}
                             for a, o in orders.items()}

    arms = list(next(iter(per_q.values())))
    groups = {"ALL": list(per_q)}
    for qid, c in classes.items():
        groups.setdefault(c, []).append(qid)

    for g in sorted(groups, key=lambda x: (x != "ALL", x)):
        qids = groups[g]
        if args.only and g != args.only:
            continue
        print(f"\n## {g}  (n={len(qids)}, k={args.k}, reranked pool = {args.base})\n")
        print(f"| arm | nDCG@{args.k} | P@1 (grade 2) | MRR@{args.k} | delta nDCG vs {args.base} [95% CI] | top-k changed | better / worse |")
        print("|---|---|---|---|---|---|---|")
        for a in arms:
            m = lambda key: sum(per_q[q][a][key] for q in qids) / len(qids)  # noqa: E731
            deltas = [per_q[q][a]["ndcg"] - per_q[q][args.base]["ndcg"] for q in qids]
            d, lo, hi = bootstrap_ci(deltas, iters=5000)
            changed = [q for q in qids if set(per_q[q][a]["top"]) != set(per_q[q][args.base]["top"])]
            better = sum(1 for x in deltas if x > 1e-9)
            worse = sum(1 for x in deltas if x < -1e-9)
            ci = "" if a == args.base else f"{d:+.3f} [{lo:+.3f}, {hi:+.3f}]"
            print(f"| {a} | {m('ndcg'):.3f} | {m('p1'):.3f} | {m('mrr'):.3f} | {ci} | {len(changed)}/{len(qids)} | {better} / {worse} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
