"""Score a CANDIDATE grader against the 440 human grades before spending 4,020.

⚠⚠ The human audit of 2026-09-22 failed section 3 (grade-0 gate 75.0% against a
90% floor) and the auditor's notes named the defect: passages about the query's
TOPIC, answering a DIFFERENT QUESTION, graded as answers. Two hypotheses survive
that finding, and they cost very different amounts to act on:

  A. CAPACITY — an 8B grader cannot hold the 0/1 boundary. Fix: a bigger model.
  B. BATCH CONTEXT — grading 15 siblings in one prompt induces RELATIVE ranking,
     so the best-of-batch reads as an answer even when nothing answers. Fix: one
     passage per call, which is free.

⚠ Hypothesis B is not speculation here. This repo already recorded the same
hazard for the other reranker: "int8 cross-encoder scores depend on batch
composition; one passage per call."

Both are separable on the SAME 440 items, so nobody has to guess.

⚠⚠ This scores against HUMAN grades, never against the old model's labels. The
old labels are the thing under suspicion.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

from .a6_draft import call as draft_call
from .a6_draft import PROVIDERS

ROOT = Path(__file__).resolve().parent.parent
PACK = "audit-a6-2026-09-20"
GATES = ((0, "human said 0", 0.90, lambda h: h == 0),
         (2, "human said 1 or 2", 0.80, lambda h: h >= 1))


def gold() -> dict[tuple[str, str, str], int]:
    """(corpus, qid, section_id) -> the human grade. The only truth here."""
    a = ROOT / "audit"
    key = json.loads((a / f"{PACK}.key.json").read_text(encoding="utf-8"))
    out = {}
    for row in csv.DictReader((a / f"{PACK}.csv").open(encoding="utf-8")):
        g = row["human_grade"].strip()
        if g in ("0", "1", "2"):
            k = key[row["item"]]
            out[(k["corpus"], k["qid"], k["section_id"])] = int(g)
    return out


def _task_parts(md: str) -> tuple[str, dict[str, str]]:
    """Split a drafting task into its header (query + guidelines) and passages."""
    head, _, rest = md.partition("# Passages")
    blocks = {}
    for m in re.finditer(r"^## (c\d+)\n(.*?)(?=^## c\d+\n|\Z)", rest, re.M | re.S):
        blocks[m.group(1)] = m.group(2).strip()
    return head.rstrip(), blocks


def run(model: str, mode: str, limit: int = 0) -> None:
    g = gold()
    want: dict[tuple[str, str], set[str]] = {}
    for (corpus, qid, sec) in g:
        want.setdefault((corpus, qid), set()).add(sec)
    tasks = sorted(want)
    if limit:
        tasks = tasks[:limit]
    print(f"grader {model!r} | mode {mode} | {len(tasks)} queries "
          f"covering {sum(len(want[t]) for t in tasks)} audited passages")

    pred: dict[tuple[str, str, str], int] = {}
    bad = 0
    for n, (corpus, qid) in enumerate(tasks, 1):
        d = ROOT / "label_tasks" / corpus
        keymap = json.loads((d / "keymap.json").read_text(encoding="utf-8"))[qid]
        head, blocks = _task_parts((d / f"{qid}.md").read_text(encoding="utf-8"))
        need = {k: s for k, s in keymap.items() if s in want[(corpus, qid)]}
        try:
            if mode == "batch":
                # Production shape: every sibling visible in one prompt.
                out, _, _ = draft_call((d / f"{qid}.md").read_text(encoding="utf-8"), model=model)
                got = out.get("grades", out)
                for k, sec in need.items():
                    cell = got.get(k)
                    v = cell.get("g") if isinstance(cell, dict) else cell
                    if v in (0, 1, 2):
                        pred[(corpus, qid, sec)] = int(v)
                    else:
                        bad += 1
            else:
                # ⚠ One passage per call. The passage is relabelled c01 so the
                # model cannot infer a position, and no sibling is present.
                for k, sec in need.items():
                    prompt = f"{head}\n\n# Passages\n\n## c01\n\n{blocks[k]}\n"
                    out, _, _ = draft_call(prompt, model=model)
                    got = out.get("grades", out)
                    cell = got.get("c01", got.get(k))
                    v = cell.get("g") if isinstance(cell, dict) else cell
                    if v in (0, 1, 2):
                        pred[(corpus, qid, sec)] = int(v)
                    else:
                        bad += 1
        except SystemExit as e:
            print(f"  FAILED {corpus}/{qid}: {e}", flush=True)
            bad += len(need)
        if n % 20 == 0:
            print(f"  {n}/{len(tasks)} queries, {len(pred)} graded", flush=True)

    pairs = [(pred[k], g[k]) for k in pred]
    print(f"\n{len(pairs)} of {sum(len(want[t]) for t in tasks)} passages graded"
          f"{f'; {bad} unusable' if bad else ''}")
    if not pairs:
        print("nothing to score")
        return
    exact = sum(1 for m, h in pairs if m == h) / len(pairs)
    print(f"exact agreement with the human: {exact:.1%}")
    for gr in (0, 1, 2):
        sub = [h for m, h in pairs if m == gr]
        if sub:
            c = Counter(sub)
            print(f"  grader {gr}: n={len(sub):3}  human 0/1/2 = {c[0]}/{c[1]}/{c[2]}")
    print()
    verdicts = []
    for gr, label, floor, ok in GATES:
        sub = [h for m, h in pairs if m == gr]
        if not sub:
            print(f"GATE grader {gr}: NO DATA")
            verdicts.append(False)
            continue
        rate = sum(ok(h) for h in sub) / len(sub)
        verdicts.append(rate >= floor)
        print(f"GATE grader {gr}: {label} in {rate:.1%} of n={len(sub)} "
              f"(floor {floor:.0%}) -> {'PASS' if rate >= floor else 'FAIL'}")
    sub = [h for m, h in pairs if m == 1]
    if sub:
        c = Counter(sub)
        print(f"grader 1 (reported): exact {c[1]/len(sub):.1%} of n={len(sub)}")
    print()
    print("VALIDATION: " + ("PASS — this grader clears section 3 on the audited sample."
                            if all(verdicts) else
                            "FAIL — do not relabel 4,020 pairs with this grader."))
    print("⚠ A pass here is on 440 items the human judged, not a section-3 pass. "
          "Relabelling still needs a FRESH audit draw.")


def main(argv=None) -> int:
    # ⚠⚠ Force UTF-8 stdio. On Windows stdout is the console stream on a
    # terminal and the LOCALE stream (cp1252) when PIPED, so this module printed
    # its whole verdict and then died on the trailing caveat the moment anyone
    # redirected it to a file. Measured here on the first smoke run, in the same
    # week the identical defect was fixed in bench/audit.py and not carried over.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="ollama tag, e.g. gemma4:26b")
    ap.add_argument("--mode", choices=["batch", "single"], default="batch")
    ap.add_argument("--limit", type=int, default=0, help="queries, for a smoke run")
    a = ap.parse_args(argv)
    run(a.model, a.mode, a.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
