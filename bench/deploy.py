"""Deployment measurements for the [rerank] sketch, dev pools only:
int8 through fastembed's add_custom_model vs onnxruntime directly, capped
threads, and cold first-query cost (one fresh process per sample).
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO, INT8 = "Xenova/ms-marco-MiniLM-L-6-v2", "onnx/model_quantized.onnx"


def make(backend: str, threads: int | None):
    """Returns score(query, texts) -> list[float]; length-sorted batches of 4."""
    if backend == "fastembed":
        from fastembed.common.model_description import ModelSource
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        name = "jdoc/ms-marco-MiniLM-L-6-v2-int8"
        try:
            TextCrossEncoder.add_custom_model(model=name, sources=ModelSource(hf=REPO), model_file=INT8)
        except ValueError:
            pass
        m = TextCrossEncoder(model_name=name, threads=threads)

        def score(query, texts):
            order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
            raw = list(m.rerank(query, [texts[i] for i in order], batch_size=4))
            out = [0.0] * len(texts)
            for i, v in zip(order, raw):
                out[i] = float(v)
            return out
        return score

    from .levers import Ort
    m = Ort("int8", 512, threads)
    m.bucket = 4
    return m.score


def pools(corpus: str):
    from .labeling import load_pools
    from .providers import passage_text
    for row in load_pools(next((ROOT / "pools").glob(f"{corpus}.n*.jsonl"))):
        ids = row["rankings"]["A-hyb"]
        yield row["qid"], row["query"], ids, [passage_text(row["candidates"][i]) for i in ids]


def cold(backend: str, threads: int | None) -> dict:
    t0 = time.perf_counter()
    score = make(backend, threads)
    t1 = time.perf_counter()
    items = list(pools("k8s"))[:4]
    times = []
    for _, q, _, texts in items:
        t = time.perf_counter()
        score(q, texts)
        times.append((time.perf_counter() - t) * 1000)
    return {"load_ms": (t1 - t0) * 1000, "first_query_ms": times[0], "later_ms": times[1:]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cold", nargs=2, metavar=("BACKEND", "THREADS"))
    a = ap.parse_args(argv)
    if a.cold:
        print(json.dumps(cold(a.cold[0], int(a.cold[1]) or None)))
        return 0

    ref = {c: json.loads((ROOT / "runs" / "scores" / f"{c}.onnx-int8.json").read_text())["queries"] for c in ("fastapi", "k8s")}
    print("| backend | threads | corpus | p50 ms | p95 ms | top-5 identical to harness int8 | max score drift | torch loaded |")
    print("|---|---|---|---|---|---|---|---|")
    for backend in ("fastembed", "ort"):
        for threads in (2, 4, None):
            score = make(backend, threads)
            for corpus in ("fastapi", "k8s"):
                lat, same, n, drift = [], 0, 0, 0.0
                for qid, q, ids, texts in pools(corpus):
                    t = time.perf_counter()
                    raw = score(q, texts)
                    lat.append((time.perf_counter() - t) * 1000)
                    mine = sorted(ids, key=lambda i: -raw[ids.index(i)])
                    theirs = sorted(ids, key=lambda i: -ref[corpus][qid]["scores"][i])
                    same += mine[:5] == theirs[:5]
                    drift = max(drift, max(abs(1 / (1 + math.exp(-raw[j])) - ref[corpus][qid]['scores'][i]) for j, i in enumerate(ids)))
                    n += 1
                lat = sorted(lat[1:])
                print(f"| {backend} | {threads or 'default'} | {corpus} | {lat[len(lat) // 2]:.0f} | {lat[int(.95 * len(lat))]:.0f} | {same}/{n} | {drift:.3f} | {'torch' in sys.modules} |", flush=True)

    print("\n| backend | threads | load ms | first query ms | later queries ms | (3 fresh processes, model already downloaded) |")
    print("|---|---|---|---|---|---|")
    for backend in ("fastembed", "ort"):
        for threads in (2, 4):
            for _ in range(3):
                out = subprocess.run([sys.executable, "-m", "bench.deploy", "--cold", backend, str(threads)],
                                     capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
                r = json.loads(out.stdout.strip().splitlines()[-1])
                print(f"| {backend} | {threads} | {r['load_ms']:.0f} | {r['first_query_ms']:.0f} | {', '.join(f'{x:.0f}' for x in r['later_ms'])} | |", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
