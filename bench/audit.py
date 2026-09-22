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

from .labeling import GUIDELINES, GUIDELINES_A6, load_pools

ROOT = Path(__file__).resolve().parent.parent
QUOTA = {2: 0.35, 1: 0.35, 0: 0.30}


def _item(corpus: str, pools: dict, row: dict, grade: int) -> dict:
    p = pools[row["qid"]]
    return {"corpus": corpus, "class": p["class"], "query": p["query"], "llm_grade": grade,
            "qid": row["qid"], "section_id": row["section_id"],
            "cand": p["candidates"][row["section_id"]]}


def _round_robin(rows: list[dict], rng: random.Random) -> dict:
    """Bucket rows by query so no single query can dominate a stratum."""
    rng.shuffle(rows)
    per_q = defaultdict(list)
    for r in rows:
        per_q[r["qid"]].append(r)
    return per_q


def sample(corpora: list[str], per_corpus: int, seed: int, name: str,
           rubric: str = "default", grade1_extra: int = 0) -> int:
    rng = random.Random(seed)
    items: list[dict] = []
    chosen: set[tuple[str, str, str]] = set()
    pools_by_corpus: dict[str, dict] = {}
    g1_by_corpus: dict[str, list] = {}
    for corpus in corpora:
        pools = {r["qid"]: r for r in load_pools(next((ROOT / "pools").glob(f"{corpus}.n*.jsonl")))}
        pools_by_corpus[corpus] = pools
        by_grade = defaultdict(list)
        for line in (ROOT / "labels" / f"{corpus}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            by_grade[r["grade"]].append(r)
        g1_by_corpus[corpus] = by_grade[1]
        short = 0
        for g in (2, 1, 0):  # grade 0 last so it absorbs any shortfall
            want = round(per_corpus * QUOTA[g]) + (short if g == 0 else 0)
            per_q = _round_robin(by_grade[g][:], rng)
            picked = []
            while len(picked) < want and any(per_q.values()):
                for q in list(per_q):
                    if per_q[q] and len(picked) < want:
                        picked.append(per_q[q].pop())
            short += want - len(picked) if g != 0 else 0
            for r in picked:
                items.append(_item(corpus, pools, r, g))
                chosen.add((corpus, r["qid"], r["section_id"]))
    quota_n = len(items)

    # ⚠⚠ GRADE-1 OVERSAMPLE, pre-registered at +40 (section 7). Grade 1 is the
    # stratum the A6 rubric rewrote and the one the A1 second-model audit agreed
    # with only 43% of the time, so it is judged with more power than the 35%
    # quota alone gives it. ⚠ Never re-pick an item the quota already took: a
    # duplicate would be graded twice by the human and counted twice by `agree`.
    added = 0
    if grade1_extra:
        avail = {c: _round_robin([r for r in g1_by_corpus[c]
                                  if (c, r["qid"], r["section_id"]) not in chosen], rng)
                 for c in corpora}
        while added < grade1_extra and any(any(q.values()) for q in avail.values()):
            for corpus in corpora:
                if added >= grade1_extra:
                    break
                per_q = avail[corpus]
                for q in list(per_q):
                    if per_q[q]:
                        r = per_q[q].pop()
                        items.append(_item(corpus, pools_by_corpus[corpus], r, 1))
                        chosen.add((corpus, r["qid"], r["section_id"]))
                        added += 1
                        break
        if added < grade1_extra:
            print(f"⚠ grade-1 oversample SHORT: wanted {grade1_extra}, added {added}")

    # ⚠⚠ Shuffle AFTER the oversample, not before. Appending 40 grade-1 items to
    # the tail would tell the auditor the tail is one stratum, and the pack's
    # only defence against anchoring is that they cannot tell which is which.
    rng.shuffle(items)
    # ⚠⚠ The auditor must read the SAME rubric the labeller was given. Handing
    # over the default text while the labels were drafted under the A6 grade-1
    # wording measures rubric drift and reports it as label noise.
    guidelines = GUIDELINES_A6 if rubric == "a6" else GUIDELINES
    out = ROOT / "audit"
    out.mkdir(exist_ok=True)
    md = [f"# Label audit\n\nGrade each item 0, 1 or 2 in `{name}.csv`. Do not open `{name}.key.json` first.\n\n## Guidelines\n\n{guidelines}\n"]
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
    print(f"{len(items)} items ({quota_n} quota + {added} grade-1 oversample)"
          f" | rubric {rubric} | seed {seed}")
    print(" ", dict(sorted(Counter((k["corpus"], k["llm_grade"]) for k in key.values()).items())))
    return len(items)


def agree(name: str) -> None:
    key = json.loads((ROOT / "audit" / f"{name}.key.json").read_text(encoding="utf-8"))
    pairs = []
    with (ROOT / "audit" / f"{name}.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["human_grade"].strip() in ("0", "1", "2"):
                pairs.append((key[row["item"]]["llm_grade"], int(row["human_grade"])))
    print(f"{len(pairs)} of {len(key)} items graded")
    if len(pairs) < len(key):
        # ⚠ A partially filled sheet is not a verdict. The strata are quota'd, so
        # whichever items were skipped bias whichever gate they belonged to.
        print("⚠ INCOMPLETE — gates below describe the graded subset only.")
    by_llm = {g: [h for l, h in pairs if l == g] for g in (0, 1, 2)}
    for g in (0, 1, 2):
        sub = by_llm[g]
        if sub:
            c = Counter(sub)
            print(f"LLM grade {g}: n={len(sub)}  human says 0/1/2 = {c[0]}/{c[1]}/{c[2]}  "
                  f"exact agreement {c[g] / len(sub):.0%}")

    # ⚠⚠ THE GATES ARE NOT EXACT AGREEMENT, and reading them as such fails a pass
    # that section 3 accepts. Grade 0 must be confirmed as 0 (a false positive in
    # the label set is what poisons a ranking metric); grade 2 only has to be
    # USEFUL, so a human 1 counts. Pre-registered in LABEL-DESIGN-A6 section 7.
    print()
    verdicts = []
    for g, label, floor, ok in ((0, "human says 0", 0.90, lambda h: h == 0),
                                (2, "human says 1 or 2", 0.80, lambda h: h >= 1)):
        sub = by_llm[g]
        if not sub:
            print(f"GATE grade {g}: NO DATA")
            verdicts.append(False)
            continue
        rate = sum(ok(h) for h in sub) / len(sub)
        passed = rate >= floor
        verdicts.append(passed)
        print(f"GATE grade {g}: {label} in {rate:.1%} of n={len(sub)} "
              f"(floor {floor:.0%}) -> {'PASS' if passed else 'FAIL'}")

    # ⚠ Grade 1 is REPORTED, never a hard kill on its own -- but under 50% exact
    # agreement after the tightened rubric is a STOP, because the rubric is then
    # the thing that failed, not the labels.
    g1_stop = False
    sub = by_llm[1]
    if sub:
        c = Counter(sub)
        exact = c[1] / len(sub)
        print(f"grade 1 (reported, not a gate): exact {exact:.1%} of n={len(sub)}  "
              f"confusion 0 vs {{1,2}} = {c[0]} vs {c[1] + c[2]}")
        if exact < 0.50:
            g1_stop = True
            print("⚠⚠ STOP: grade-1 exact agreement under 50% after the tightened "
                  "rubric. Revise the rubric and relabel before scoring anything.")
    rel = [(l >= 1, h >= 1) for l, h in pairs]
    if rel:
        print(f"binary (useful at all) agreement within sample: "
              f"{sum(a == b for a, b in rel) / len(rel):.0%}")
    print()
    # ⚠⚠ "No data" is NOT a FAIL, and printing one for the other is the defect
    # class this repo already named: a signal that always fires hides the case it
    # exists for. An unfilled sheet reads as the labels having failed an audit
    # nobody has performed, which is the one reading that could get them thrown
    # out on no evidence at all.
    if not pairs:
        print("SECTION 3: NOT AUDITED — no item graded yet. This is not a "
              "verdict on the labels.")
    elif g1_stop:
        # ⚠⚠ Both gates can PASS while grade 1 is noise -- measured on a synthetic
        # sheet that called every grade-1 item 0: gates 100%/100%, grade-1 exact
        # 0%. Section 7 makes that a STOP before scoring, so the summary must not
        # print PASS underneath its own stop warning.
        print("SECTION 3: STOP — both gates pass, but grade-1 exact agreement is "
              "under 50%. Revise the rubric and relabel before scoring.")
    elif not all(verdicts):
        print("SECTION 3: FAIL — fix guidelines, relabel, re-audit. "
              "A6 labels are NOT evidence until the gates pass.")
    elif len(pairs) < len(key):
        print(f"SECTION 3: gates pass on the {len(pairs)} graded items, but "
              f"{len(key) - len(pairs)} are unfilled. NOT a pass — finish the "
              "sheet, because the skipped items bias the gate they belonged to.")
    else:
        print("SECTION 3: PASS — A6 labels are evidence.")


def main(argv=None) -> int:
    # ⚠⚠ Force UTF-8 stdio. On Windows `sys.stdout` is the CONSOLE stream on a
    # terminal and the LOCALE stream (cp1252) when PIPED, so this module printed
    # its verdict by hand and died with UnicodeEncodeError the moment anyone
    # redirected it to a file -- which is exactly how an auditor keeps a record.
    # Measured 2026-09-21: `agree` traced back on the first ⚠ it tried to print.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):  # not a reconfigurable text stream
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "agree"])
    ap.add_argument("--corpora", default="fastapi,k8s")
    ap.add_argument("--per-corpus", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--name", default="audit-2026-09-19")
    ap.add_argument("--rubric", choices=["default", "a6"], default="default",
                    help="a6 hands the auditor the tightened grade-1 text")
    ap.add_argument("--grade1-extra", type=int, default=0,
                    help="extra grade-1 items beyond the quota (A6: 40)")
    a = ap.parse_args(argv)
    if a.cmd == "sample":
        sample(a.corpora.split(","), a.per_corpus, a.seed, a.name,
               a.rubric, a.grade1_extra)
    else:
        agree(a.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
