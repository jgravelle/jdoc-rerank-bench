"""Blind label tasks (BENCH-004/005): pooled candidates from every baseline arm,
shuffled, under opaque keys. The labeler sees no ids, paths, ranks or arm names.

  export: pools/<corpus>.n<N>.jsonl -> label_tasks/<corpus>/<qid>.md + keymap.json
  collect: label_tasks/<corpus>/<qid>.labels.json -> labels/<corpus>.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GUIDELINES = """\
Grade each passage for the query. Judge only what the passage itself says.

2 = directly answers: states information a reader could cite to answer the query.
1 = partially useful: gives real but incomplete help (a needed building block,
    a closely related mechanism the answer depends on).
0 = not useful: shares topic or vocabulary but does not help answer the query;
    or is navigational, boilerplate, a heading with no content, or release notes.

Same words as the query is not evidence of relevance. Most passages are 0.
If the documentation cannot answer the query at all, every passage is 0.
"""


def load_pools(path: Path) -> list[dict]:
    return [r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines()) if "_run" not in r]


def export(pool_file: Path, out_dir: Path, seed: int = 0) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    keymap = {}
    for row in load_pools(pool_file):
        ids = sorted(row["candidates"])
        random.Random(f"{seed}:{row['qid']}").shuffle(ids)
        keymap[row["qid"]] = {f"c{i + 1:02d}": sid for i, sid in enumerate(ids)}
        parts = [f"# Query\n\n{row['query']}\n\n# Guidelines\n\n{GUIDELINES}\n# Passages\n"]
        for key, sid in keymap[row["qid"]].items():
            c = row["candidates"][sid]
            parts.append(f"\n## {key}\n\nHeading: {' > '.join(c['heading_path'][1:]) or c['title']}\n\n{c['body']}\n")
        (out_dir / f"{row['qid']}.md").write_text("".join(parts), encoding="utf-8")
    (out_dir / "keymap.json").write_text(json.dumps(keymap), encoding="utf-8")
    return len(keymap)


def collect(task_dir: Path, out_file: Path) -> tuple[int, list[str]]:
    keymap = json.loads((task_dir / "keymap.json").read_text(encoding="utf-8"))
    n, problems = 0, []
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as fh:
        for qid, keys in keymap.items():
            f = task_dir / f"{qid}.labels.json"
            if not f.exists():
                problems.append(f"{qid}: missing")
                continue
            got = json.loads(f.read_text(encoding="utf-8"))
            bad = [k for k in keys if got.get(k) not in (0, 1, 2)]
            if bad or set(got) - set(keys):
                problems.append(f"{qid}: bad or unknown keys {bad or sorted(set(got) - set(keys))}")
                continue
            for k, sid in keys.items():
                fh.write(json.dumps({"qid": qid, "section_id": sid, "grade": got[k]}) + "\n")
                n += 1
    return n, problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["export", "collect"])
    ap.add_argument("--pools", required=True)
    args = ap.parse_args(argv)
    pool_file = Path(args.pools)
    corpus = pool_file.name.split(".")[0]
    task_dir = ROOT / "label_tasks" / corpus
    if args.cmd == "export":
        print(export(pool_file, task_dir), "tasks ->", task_dir)
    else:
        n, problems = collect(task_dir, ROOT / "labels" / f"{corpus}.jsonl")
        print(n, "labels;", len(problems), "problems")
        for p in problems:
            print(" ", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
