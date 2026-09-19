"""Latency levers for the ONNX reranker, from cached pools: token cap, pool
depth, int8 weights. Talks to onnxruntime directly so each lever is explicit.

Quality is nDCG@k delta vs the base arm with a paired bootstrap; latency is
wall clock per query on CPU for one pool of DEPTH candidates.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from .labeling import load_pools
from .metrics import bootstrap_ci, ndcg_at_k
from .providers import passage_text
from .report import rerank, rrf

ROOT = Path(__file__).resolve().parent.parent
REPO = "Xenova/ms-marco-MiniLM-L-6-v2"
FILES = {"fp32": "onnx/model.onnx", "int8": "onnx/model_quantized.onnx"}


class Ort:
    def __init__(self, weights: str, max_tokens: int, threads: int | None = None):
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        self.tok = Tokenizer.from_file(hf_hub_download(REPO, "tokenizer.json"))
        self.tok.enable_truncation(max_length=max_tokens)
        self.tok.enable_padding()
        so = ort.SessionOptions()
        if threads:
            so.intra_op_num_threads, so.inter_op_num_threads = threads, 1
        self.sess = ort.InferenceSession(hf_hub_download(REPO, FILES[weights]), sess_options=so,
                                         providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.sess.get_inputs()}

    bucket = 0  # >0: run length-sorted sub-batches so short passages skip the padding

    def score(self, query: str, texts: list[str]) -> list[float]:
        if self.bucket:
            order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
            out = [0.0] * len(texts)
            for j in range(0, len(order), self.bucket):
                idx = order[j: j + self.bucket]
                for i, v in zip(idx, self._run(query, [texts[i] for i in idx])):
                    out[i] = v
            return out
        return self._run(query, texts)

    def _run(self, query: str, texts: list[str]) -> list[float]:
        enc = self.tok.encode_batch([(query, t) for t in texts])
        feed = {"input_ids": np.array([e.ids for e in enc], dtype=np.int64),
                "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64),
                "token_type_ids": np.array([e.type_ids for e in enc], dtype=np.int64)}
        logits = self.sess.run(None, {k: v for k, v in feed.items() if k in self.inputs})[0]
        return [float(x) for x in logits.reshape(-1)]


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pools", required=True)
    ap.add_argument("--base", default="A-hyb")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--tokens", default="512,256,128")
    ap.add_argument("--depths", default="20,15,10")
    ap.add_argument("--weights", default="fp32,int8")
    ap.add_argument("--bucket", type=int, default=0)
    args = ap.parse_args(argv)

    pool_file = Path(args.pools)
    corpus = pool_file.name.split(".")[0]
    labels = defaultdict(dict)
    for line in (ROOT / "labels" / f"{corpus}.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        labels[r["qid"]][r["section_id"]] = r["grade"]
    rows = [r for r in load_pools(pool_file) if r["class"] != "Q6"]
    depths = [int(d) for d in args.depths.split(",")]

    print(f"n={len(rows)} queries, k={args.k}, base={args.base}, model={REPO}\n")
    print("| weights | max tokens | depth | p50 ms | p95 ms | delta nDCG sort [95% CI] | delta nDCG RRF [95% CI] | worse sort / RRF |")
    print("|---|---|---|---|---|---|---|---|")
    results = []
    for w in args.weights.split(","):
        for mt in (int(t) for t in args.tokens.split(",")):
            m = Ort(w, mt)
            m.bucket = args.bucket
            first = rows[0]
            m.score(first["query"], [passage_text(first["candidates"][i]) for i in first["rankings"][args.base]])  # warm-up
            for depth in depths:
                lat, d_sort, d_rrf = [], [], []
                for row in rows:
                    base = row["rankings"][args.base][:depth]
                    texts = [passage_text(row["candidates"][i]) for i in base]
                    t0 = time.perf_counter()
                    raw = m.score(row["query"], texts)
                    lat.append((time.perf_counter() - t0) * 1000)
                    sc = dict(zip(base, raw))
                    lab = labels[row["qid"]]
                    b = ndcg_at_k(row["rankings"][args.base], lab, args.k)
                    d_sort.append(ndcg_at_k(rerank(base, sc), lab, args.k) - b)
                    d_rrf.append(ndcg_at_k(rrf(base, sc), lab, args.k) - b)
                s, r = bootstrap_ci(d_sort, iters=5000), bootstrap_ci(d_rrf, iters=5000)
                worse = f"{sum(x < -1e-9 for x in d_sort)} / {sum(x < -1e-9 for x in d_rrf)}"
                print(f"| {w} | {mt} | {depth} | {pct(lat, .5):.0f} | {pct(lat, .95):.0f} | "
                      f"{s[0]:+.3f} [{s[1]:+.3f}, {s[2]:+.3f}] | {r[0]:+.3f} [{r[1]:+.3f}, {r[2]:+.3f}] | {worse} |", flush=True)
                results.append({"weights": w, "max_tokens": mt, "depth": depth, "p50": pct(lat, .5), "p95": pct(lat, .95),
                                "sort": s, "rrf": r})
    out = ROOT / "runs" / f"{corpus}.levers.b{args.bucket}.json"
    out.write_text(json.dumps({"torch_loaded": "torch" in sys.modules, "results": results}), encoding="utf-8")
    print(f"\ntorch loaded: {'torch' in sys.modules}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
