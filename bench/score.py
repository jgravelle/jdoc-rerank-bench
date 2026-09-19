"""Score cached pools with a provider and cache the scores (replayable arms)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .labeling import load_pools
from .providers import REGISTRY

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pools", required=True)
    ap.add_argument("--provider", required=True, choices=sorted(REGISTRY))
    ap.add_argument("--model", default=None)
    args = ap.parse_args(argv)

    provider = REGISTRY[args.provider](args.model) if args.model else REGISTRY[args.provider]()
    pool_file = Path(args.pools)
    out = {"_run": {"provider": provider.name, "version": provider.version, "pools": pool_file.name}, "queries": {}}
    for row in load_pools(pool_file):
        # Timed per baseline pool: what a user pays is one pool of N, not the union.
        timings = {}
        for arm, ids in row["rankings"].items():
            t0 = time.perf_counter()
            provider.score(row["query"], {i: row["candidates"][i] for i in ids})
            timings[arm] = round((time.perf_counter() - t0) * 1000, 1)
        out["queries"][row["qid"]] = {"scores": provider.score(row["query"], row["candidates"]), "latency_ms": timings}
    dest = ROOT / "runs" / "scores" / f"{pool_file.name.split('.')[0]}.{provider.name if not args.model else args.model.split('/')[-1]}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out), encoding="utf-8")
    print(f"{len(out['queries'])} queries -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
