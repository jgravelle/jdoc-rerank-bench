"""Human audit of the LLM labels (BENCH-006).

  sample: stratified by LLM grade, spread across queries, grades hidden.
          audit/<name>.md is what the auditor reads, audit/<name>.csv is what
          they fill in, audit/<name>.key.json stays closed until they finish.
  agree:  agreement PER STRATUM. The sample oversamples grades 1 and 2, so a
          pooled agreement rate would describe the sample, not the label set.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .labeling import GUIDELINES, load_pools

ROOT = Path(__file__).resolve().parent.parent
QUOTA = {2: 0.35, 1: 0.35, 0: 0.30}


def sample(corpora: list[str], per_corpus: int, seed: int, name: str) -> int:
    rng = random.Random(seed)
    items = []
    for corpus in corpora:
        pools = {r["qid"]: r for r in load_pools(next((ROOT / "pools").glob(f"{corpus}.n*.jsonl")))}
        by_grade = defaultdict(list)
        for line in (ROOT / "labels" / f"{corpus}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            by_grade[r["grade"]].append(r)
        short = 0
        for g in (2, 1, 0):  # grade 0 last so it absorbs any shortfall
            want = round(per_corpus * QUOTA[g]) + (short if g == 0 else 0)
            rows = by_grade[g][:]
            rng.shuffle(rows)
            # Round-robin over queries so one query cannot dominate a stratum.
            per_q = defaultdict(list)
            for r in rows:
                per_q[r["qid"]].append(r)
            picked = []
            while len(picked) < want and any(per_q.values()):
                for q in list(per_q):
                    if per_q[q] and len(picked) < want:
                        picked.append(per_q[q].pop())
            short += want - len(picked) if g != 0 else 0
            for r in picked:
                p = pools[r["qid"]]
                items.append({"corpus": corpus, "class": p["class"], "query": p["query"], "llm_grade": g,
                              "qid": r["qid"], "section_id": r["section_id"], "cand": p["candidates"][r["section_id"]]})
    rng.shuffle(items)
    out = ROOT / "audit"
    out.mkdir(exist_ok=True)
    md = [f"# Label audit\n\nGrade each item 0, 1 or 2 in `{name}.csv`. Do not open `{name}.key.json` first.\n\n## Guidelines\n\n{GUIDELINES}\n"]
    key = {}
    with (out / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["item", "human_grade", "note"])
        for i, it in enumerate(items, 1):
            iid = f"A{i:03d}"
            w.writerow([iid, "", ""])
            key[iid] = {k: it[k] for k in ("corpus", "class", "qid", "section_id", "llm_grade")}
            head = " > ".join(it["cand"]["heading_path"][1:]) or it["cand"]["title"]
            md.append(f"\n---\n\n## {iid}\n\n**Query:** {it['query']}\n\n**Heading:** {head}\n\n{it['cand']['body']}\n")
    (out / f"{name}.md").write_text("".join(md), encoding="utf-8")
    (out / f"{name}.key.json").write_text(json.dumps(key), encoding="utf-8")
    print(len(items), "items;", dict(Counter((k["corpus"], k["llm_grade"]) for k in key.values())))
    return len(items)


def agree(name: str) -> None:
    key = json.loads((ROOT / "audit" / f"{name}.key.json").read_text(encoding="utf-8"))
    pairs = []
    with (ROOT / "audit" / f"{name}.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["human_grade"].strip() in ("0", "1", "2"):
                pairs.append((key[row["item"]]["llm_grade"], int(row["human_grade"])))
    print(f"{len(pairs)} of {len(key)} items graded")
    for g in (0, 1, 2):
        sub = [h for l, h in pairs if l == g]
        if sub:
            c = Counter(sub)
            print(f"LLM grade {g}: n={len(sub)}  human says 0/1/2 = {c[0]}/{c[1]}/{c[2]}  exact agreement {c[g] / len(sub):.0%}")
    rel = [(l >= 1, h >= 1) for l, h in pairs]
    if rel:
        print(f"binary (useful at all) agreement within sample: {sum(a == b for a, b in rel) / len(rel):.0%}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "agree"])
    ap.add_argument("--corpora", default="fastapi,k8s")
    ap.add_argument("--per-corpus", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--name", default="audit-2026-09-19")
    a = ap.parse_args(argv)
    sample(a.corpora.split(","), a.per_corpus, a.seed, a.name) if a.cmd == "sample" else agree(a.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
