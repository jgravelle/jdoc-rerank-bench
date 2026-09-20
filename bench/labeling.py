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

# A6 §9 step 2. ⚠⚠ The grade-1 line above scored **43% exact agreement** in the
# 2026-09-19 second-model audit, which is why A6 replaces it. Grades 0 and 2 are
# carried over VERBATIM: rewriting grade 2 toward Jev's `true` criterion is the
# shared-method bias A3 flagged, so the pre-Jev wording is load-bearing.
# ⚠ `GUIDELINES` is NOT edited in place — A3's exports and labels were produced
# under it, and a study's rubric is part of its record.
# Authority: results/RUBRIC-A6-grade1.md, frozen.
GUIDELINES_A6 = """\
Grade each passage for the query. Judge only what the passage itself says.

2 = directly answers: states information a reader could cite to answer the query.

1 = necessary but incomplete. The passage supplies at least one concrete fact,
    API, constraint, or step that a correct answer to the query MUST use or obey,
    but it does not by itself state a citable answer to the query. A competent
    reader who had ONLY this passage would still need at least one other passage
    to finish the answer. All three must hold:
      - Necessity: removing this passage's specific content would force a wrong
        or incomplete answer (a missing required parameter, flag, error code,
        ordering constraint, security caveat, or named API).
      - Substance: it states a usable rule or mechanism, not a heading, a table
        of contents, nav chrome, a version banner, or a "see also" list.
      - Incompleteness: it does not fully answer the query on its own.

0 = not useful: shares topic or vocabulary but does not help answer the query;
    or is navigational, boilerplate, a heading with no content, or release notes.
    Mark 0, not 1, for any of these:
      - Topic-only overlap: same product or area, but no fact the answer depends
        on (background, motivation, history, marketing).
      - Adjacent feature: a sibling feature not required to answer THIS query.
      - Example without the rule: code using a related API without stating the
        constraint the query asks about.
      - "Would be nice" context: helpful for understanding the ecosystem but not
        load-bearing for this answer.

Boundaries:
  - If a reader could cite THIS PASSAGE ALONE to answer the query, grade 2.
  - If it is load-bearing but leaves a required gap, grade 1.
  - Unsure between 1 and 2: prefer 1. Do not inflate 2.
  - Unsure between 0 and 1: prefer 0. Do not inflate 1. Partial credit requires
    necessity, not topical warmth.

Same words as the query is not evidence of relevance. Most passages are 0.
A correct-looking code sample that does not address the asked failure mode is 0.
If the documentation cannot answer the query at all, every passage is 0,
including superficially related ones.
"""


def load_pools(path: Path) -> list[dict]:
    return [r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines()) if "_run" not in r]


def export(pool_file: Path, out_dir: Path, seed: int = 0,
           guidelines: str = GUIDELINES, arm: str | None = None, depth: int = 0) -> int:
    """Blind label tasks. `arm` + `depth` restrict the judgment set.

    ⚠⚠ With no `arm`, EVERY candidate is exported — the union of all arms' top-n,
    which is 20 per query here. A6 §4.3 freezes the judgment list as
    `rankings["A-hyb"][:15]`, so A6 passes `arm="A-hyb", depth=15`. Exporting the
    union instead would label 5,360 pairs where 4,020 are needed and would put
    A-lex-only candidates in front of a labeler for a study whose baseline is
    A-hyb.
    ⚠ The shuffle is seeded per qid, so the keys stay blind but reproducible. It
    runs AFTER the restriction, so `c01` is not the top-ranked passage.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    keymap = {}
    for row in load_pools(pool_file):
        if arm:
            ranked = row["rankings"][arm]
            ids = sorted(ranked[:depth] if depth else ranked)
        else:
            ids = sorted(row["candidates"])
        random.Random(f"{seed}:{row['qid']}").shuffle(ids)
        keymap[row["qid"]] = {f"c{i + 1:02d}": sid for i, sid in enumerate(ids)}
        parts = [f"# Query\n\n{row['query']}\n\n# Guidelines\n\n{guidelines}\n# Passages\n"]
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
    ap.add_argument("--rubric", choices=["default", "a6"], default="default",
                    help="a6 uses the tightened grade-1 text from RUBRIC-A6-grade1.md")
    ap.add_argument("--arm", default=None, help="restrict the judgment set to one arm's ranking")
    ap.add_argument("--depth", type=int, default=0, help="judgment depth within --arm (A6: 15)")
    args = ap.parse_args(argv)
    pool_file = Path(args.pools)
    corpus = pool_file.name.split(".")[0]
    task_dir = ROOT / "label_tasks" / corpus
    if args.cmd == "export":
        n = export(pool_file, task_dir, guidelines=GUIDELINES_A6 if args.rubric == "a6" else GUIDELINES,
                   arm=args.arm, depth=args.depth)
        print(n, "tasks ->", task_dir)
    else:
        n, problems = collect(task_dir, ROOT / "labels" / f"{corpus}.jsonl")
        print(n, "labels;", len(problems), "problems")
        for p in problems:
            print(" ", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
