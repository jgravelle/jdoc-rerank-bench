"""Hybrid (A-hyb) vs lexical (A-lex) on every cached, labeled pool.

This is jdocmunch against itself: what a user without an embedding provider
gives up. No reranker is involved. Read from cache.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from .labeling import load_pools
from .metrics import bootstrap_ci, mrr, ndcg_at_k, precision_at_k

ROOT = Path(__file__).resolve().parent.parent
K = 5


def main() -> int:
    rows = []
    for pf in sorted((ROOT / "pools").glob("*.n20.jsonl")):
        corpus = pf.name.split(".")[0]
        lf = ROOT / "labels" / f"{corpus}.jsonl"
        if not lf.exists():
            continue
        labels = defaultdict(dict)
        for line in lf.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            labels[r["qid"]][r["section_id"]] = r["grade"]
        for row in load_pools(pf):
            if row["class"] == "Q6":
                continue
            lab, lex, hyb = labels[row["qid"]], row["rankings"]["A-lex"], row["rankings"]["A-hyb"]
            rows.append({"corpus": corpus, "class": row["class"],
                         "lex": ndcg_at_k(lex, lab, K), "hyb": ndcg_at_k(hyb, lab, K),
                         "lex_p1": precision_at_k(lex, lab, 1, min_grade=2), "hyb_p1": precision_at_k(hyb, lab, 1, min_grade=2),
                         "lex_hit": mrr(lex, lab, K, min_grade=2) > 0, "hyb_hit": mrr(hyb, lab, K, min_grade=2) > 0})

    def line(name, g):
        d = [r["hyb"] - r["lex"] for r in g]
        ci = bootstrap_ci(d, iters=5000, seed=0)
        n = len(g)
        print(f"| {name} | {n} | {sum(r['lex'] for r in g) / n:.3f} | {sum(r['hyb'] for r in g) / n:.3f} | "
              f"{ci[0]:+.3f} [{ci[1]:+.3f}, {ci[2]:+.3f}] | {sum(x > 1e-9 for x in d)} / {sum(x < -1e-9 for x in d)} | "
              f"{sum(r['lex_p1'] for r in g) / n:.0%} -> {sum(r['hyb_p1'] for r in g) / n:.0%} | "
              f"{sum(r['lex_hit'] for r in g) / n:.0%} -> {sum(r['hyb_hit'] for r in g) / n:.0%} |")

    print(f"nDCG@{K}, hybrid minus lexical, paired, ranking queries only\n")
    print("| group | n | lexical | hybrid | delta [95% CI] | hybrid better / worse | top result is a direct answer | direct answer in top 5 |")
    print("|---|---|---|---|---|---|---|---|")
    line("ALL", rows)
    for c in ("Q2", "Q3", "Q4", "Q5"):
        line(c, [r for r in rows if r["class"] == c])
    for c in sorted({r["corpus"] for r in rows}):
        line(c, [r for r in rows if r["corpus"] == c])
    return 0


if __name__ == "__main__":
    sys.exit(main())
