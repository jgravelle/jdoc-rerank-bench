"""Apply DECISION_CRITERIA.md (074dfa3 + A1 + A2) to test split 2.

A2: hybrid top 15, gated promotion at 0.95 with RRF k=10 among promoted, int8,
512 tokens, one passage per call, 4 threads. Latency: three runs over the whole
split, the run with the median p95 is judged. `--score` does the three runs.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from .labeling import load_pools
from .metrics import bootstrap_ci, ndcg_at_k, oracle_order
from .providers import passage_text
from .tune import promote

ROOT = Path(__file__).resolve().parent.parent
K, BASE, POOL, TAU, RRF_K, DECIDE = 5, "A-hyb", 15, 0.95, 10, ("Q3", "Q4", "Q5")
CORPORA = ["k8s-test2", "fastapi-test2", "packaging-test2", "django-test2", "docker-test2"]
OUT = ROOT / "runs" / "scores" / "test2.a2.json"


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def do_score():
    from .levers import Ort
    m = Ort("int8", 512, threads=4)
    m.bucket = 1
    items = [(c, r) for c in CORPORA for r in load_pools(ROOT / "pools" / f"{c}.n20.jsonl")]
    first = items[0][1]
    m.score(first["query"], [passage_text(first["candidates"][i]) for i in first["rankings"][BASE][:POOL]])
    out = {"runs": [], "scores": {}, "config": {"pool": POOL, "tau": TAU, "rrf_k": RRF_K, "threads": 4, "tokens": 512,
                                                  "weights": "int8", "per_call": 1}}
    for run in range(3):
        lat = {}
        for c, r in items:
            ids = r["rankings"][BASE][:POOL]
            t0 = time.perf_counter()
            raw = m.score(r["query"], [passage_text(r["candidates"][i]) for i in ids])
            lat[r["qid"]] = (time.perf_counter() - t0) * 1000
            out["scores"][r["qid"]] = dict(zip(ids, raw))
        out["runs"].append(lat)
        print(f"run {run + 1}: p50 {pct(lat.values(), .5):.0f} p95 {pct(lat.values(), .95):.0f}", flush=True)
    out["torch_loaded"] = "torch" in sys.modules
    OUT.write_text(json.dumps(out), encoding="utf-8")


def load(grade2_only):
    sc = json.loads(OUT.read_text(encoding="utf-8"))
    rows = []
    for c in CORPORA:
        labels = defaultdict(dict)
        for line in (ROOT / "labels" / f"{c}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            labels[r["qid"]][r["section_id"]] = (1 if r["grade"] == 2 else 0) if grade2_only else r["grade"]
        for row in load_pools(ROOT / "pools" / f"{c}.n20.jsonl"):
            full, lab = row["rankings"][BASE], labels[row["qid"]]
            pool, s = full[:POOL], sc["scores"][row["qid"]]
            b = ndcg_at_k(full, lab, K)
            new = promote(pool, s, TAU, RRF_K)
            rows.append({"corpus": c, "class": row["class"], "base": b, "delta": ndcg_at_k(new, lab, K) - b,
                         "oracle": ndcg_at_k(oracle_order(pool, lab), lab, K) - b,
                         "changed": new[:K] != pool[:K], "top": max(s.values())})
    return rows, sc


def table(rows, title):
    print(f"\n### {title}\n")
    print("| group | n | baseline nDCG@5 | oracle gain (pool 15) | delta [95% CI] | top 5 changed | better | worse | worse % |")
    print("|---|---|---|---|---|---|---|---|---|")
    groups = [("Q3-Q5 pooled", [r for r in rows if r["class"] in DECIDE])]
    groups += [(c, [r for r in rows if r["class"] == c]) for c in ("Q2", "Q3", "Q4", "Q5")]
    groups += [(c + " (Q3-Q5)", [r for r in rows if r["corpus"] == c and r["class"] in DECIDE]) for c in CORPORA]
    out = {}
    for name, g in groups:
        d = [r["delta"] for r in g]
        ci = bootstrap_ci(d, iters=5000, seed=0)
        worse = sum(x < -1e-9 for x in d)
        out[name] = (ci, worse / len(d))
        print(f"| {name} | {len(g)} | {sum(r['base'] for r in g) / len(g):.3f} | {sum(r['oracle'] for r in g) / len(g):+.3f} | "
              f"{ci[0]:+.3f} [{ci[1]:+.3f}, {ci[2]:+.3f}] | {sum(r['changed'] for r in g)} | {sum(x > 1e-9 for x in d)} | {worse} | {worse / len(d):.1%} |")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", action="store_true")
    a = ap.parse_args(argv)
    if a.score:
        do_score()
        return 0

    rows, sc = load(False)
    print(f"config: {sc['config']}  torch loaded: {sc['torch_loaded']}")
    t = table([r for r in rows if r["class"] != "Q6"], "Primary: graded labels (0/1/2)")
    table([r for r in load(True)[0] if r["class"] != "Q6"], "Sensitivity: only grade 2 counts as relevant")

    runs = [(pct(r.values(), .5), pct(r.values(), .95)) for r in sc["runs"]]
    judged = sorted(runs, key=lambda x: x[1])[1]
    print("\n### Latency, pool of 15, CPU, 4 threads, three runs over the whole split\n")
    for i, (a50, a95) in enumerate(runs, 1):
        print(f"- run {i}: p50 {a50:.0f} ms, p95 {a95:.0f} ms" + ("  <- judged (median p95)" if (a50, a95) == judged else ""))

    import math
    sig = lambda x: 1 / (1 + math.exp(-x))  # noqa: E731
    q6 = [sig(r["top"]) for r in rows if r["class"] == "Q6"]
    rest = [sig(r["top"]) for r in rows if r["class"] != "Q6"]
    print(f"\n### Out-of-corpus controls (reported, no threshold)\n\nmedian top reranked score: Q6 {pct(q6, .5):.3f} (n={len(q6)}) vs answerable {pct(rest, .5):.3f} (n={len(rest)}); "
          f"controls with nothing promoted: {sum(x < TAU for x in q6)}/{len(q6)}; answerable with nothing promoted: {sum(x < TAU for x in rest)}/{len(rest)}")

    ci, worse = t["Q3-Q5 pooled"]
    checks = [
        ("6.1 pooled lower bound > 0 and point >= +0.04", ci[1] > 0 and ci[0] >= 0.04),
        ("6.2 every corpus point > 0, none with interval entirely below zero",
         all(v[0][0] > 0 and v[0][2] >= 0 for k, v in t.items() if k.endswith("(Q3-Q5)"))),
        ("6.3 regressions <= 12% of queries (Q3-Q5 pooled)", worse <= 0.12),
        ("6.4 no class Q3-Q5 with interval entirely below zero", all(t[c][0][2] >= 0 for c in DECIDE)),
        ("6.5 latency p95 <= 500 ms and p50 <= 300 ms (median-p95 run)", judged[1] <= 500 and judged[0] <= 300),
    ]
    print("\n### Section 6 checks\n")
    for name, ok in checks:
        print(f"- {'PASS' if ok else 'FAIL'}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
