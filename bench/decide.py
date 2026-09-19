"""Apply DECISION_CRITERIA.md (074dfa3 + amendment A1) to the test split.

Primary: paired delta in nDCG@5 vs A-hyb over Q3-Q5 pooled, RRF k=60,
bootstrap 5,000 resamples, seed 0. Everything is read from cache.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from .labeling import load_pools
from .metrics import bootstrap_ci, ndcg_at_k, oracle_order
from .report import rrf

ROOT = Path(__file__).resolve().parent.parent
K, BASE, DECIDE = 5, "A-hyb", ("Q3", "Q4", "Q5")


def fmt(ci):
    return f"{ci[0]:+.3f} [{ci[1]:+.3f}, {ci[2]:+.3f}]"


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def load(corpora, provider, grade2_only):
    rows = []
    for c in corpora:
        labels = defaultdict(dict)
        for line in (ROOT / "labels" / f"{c}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            g = r["grade"]
            labels[r["qid"]][r["section_id"]] = (1 if g == 2 else 0) if grade2_only else g
        scores = json.loads((ROOT / "runs" / "scores" / f"{c}.{provider}.json").read_text(encoding="utf-8"))
        for row in load_pools(ROOT / "pools" / f"{c}.n20.jsonl"):
            q = scores["queries"][row["qid"]]
            base, lab = row["rankings"][BASE], labels[row["qid"]]
            b = ndcg_at_k(base, lab, K)
            rows.append({"corpus": c, "class": row["class"], "qid": row["qid"],
                         "base": b, "delta": ndcg_at_k(rrf(base, q["scores"]), lab, K) - b,
                         "oracle": ndcg_at_k(oracle_order(base, lab), lab, K) - b,
                         "latency": q["latency_ms"][BASE],
                         "top_score": max(q["scores"][i] for i in base)})
    return rows, scores["_run"]


def table(rows, title):
    print(f"\n### {title}\n")
    print("| group | n | baseline nDCG@5 | oracle gain | delta, RRF k=60 [95% CI] | better | worse | worse % |")
    print("|---|---|---|---|---|---|---|---|")
    groups = [("Q3-Q5 pooled", [r for r in rows if r["class"] in DECIDE])]
    groups += [(c, [r for r in rows if r["class"] == c]) for c in ("Q2", "Q3", "Q4", "Q5")]
    groups += [(c + " (Q3-Q5)", [r for r in rows if r["corpus"] == c and r["class"] in DECIDE])
               for c in sorted({r["corpus"] for r in rows})]
    out = {}
    for name, g in groups:
        d = [r["delta"] for r in g]
        ci = bootstrap_ci(d, iters=5000, seed=0)
        worse = sum(x < -1e-9 for x in d)
        out[name] = (ci, worse / len(d))
        print(f"| {name} | {len(g)} | {sum(r['base'] for r in g) / len(g):.3f} | {sum(r['oracle'] for r in g) / len(g):+.3f} | "
              f"{fmt(ci)} | {sum(x > 1e-9 for x in d)} | {worse} | {worse / len(d):.1%} |")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpora", default="k8s-test,fastapi-test,packaging-test,django-test")
    ap.add_argument("--provider", default="onnx-int8-b1")
    a = ap.parse_args(argv)
    corpora = a.corpora.split(",")

    rows, run = load(corpora, a.provider, grade2_only=False)
    print(f"provider: {run['provider']}  version: {run['version']}  torch loaded: {run.get('torch_loaded')}")
    main_t = table([r for r in rows if r["class"] != "Q6"], "Primary: graded labels (0/1/2)")
    rows2, _ = load(corpora, a.provider, grade2_only=True)
    table([r for r in rows2 if r["class"] != "Q6"], "Sensitivity: only grade 2 counts as relevant")

    lat = [r["latency"] for r in rows]
    print(f"\n### Latency, one pool of 20, CPU\n\np50 {pct(lat, .5):.0f} ms, p95 {pct(lat, .95):.0f} ms, max {max(lat):.0f} ms (n={len(lat)})")
    for c in corpora:
        l = [r["latency"] for r in rows if r["corpus"] == c]
        print(f"- {c}: p50 {pct(l, .5):.0f}, p95 {pct(l, .95):.0f}")

    q6 = [r["top_score"] for r in rows if r["class"] == "Q6"]
    rest = [r["top_score"] for r in rows if r["class"] != "Q6"]
    print(f"\n### Out-of-corpus controls (reported, no threshold)\n\ntop reranked score, median: Q6 {pct(q6, .5):.3f} (n={len(q6)}) vs answerable classes {pct(rest, .5):.3f} (n={len(rest)})")

    pooled_ci, pooled_worse = main_t["Q3-Q5 pooled"]
    checks = [
        ("6.1 pooled lower bound > 0 and point >= +0.04", pooled_ci[1] > 0 and pooled_ci[0] >= 0.04),
        ("6.2 every corpus point > 0, none with interval entirely below zero",
         all(v[0][0] > 0 and v[0][2] >= 0 for k, v in main_t.items() if k.endswith("(Q3-Q5)"))),
        ("6.3 regressions <= 12% of queries (Q3-Q5 pooled)", pooled_worse <= 0.12),
        ("6.4 no class Q3-Q5 with interval entirely below zero", all(main_t[c][0][2] >= 0 for c in DECIDE)),
        ("6.5 latency p95 <= 500 ms and p50 <= 300 ms", pct(lat, .95) <= 500 and pct(lat, .5) <= 300),
    ]
    print("\n### Section 6 checks\n")
    for name, ok in checks:
        print(f"- {'PASS' if ok else 'FAIL'}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
