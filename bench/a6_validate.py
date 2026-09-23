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
import atexit
import csv
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

from . import a6_draft
from .a6_draft import call as draft_call
from .a6_draft import PROVIDERS

ROOT = Path(__file__).resolve().parent.parent
PACK = "audit-a6-2026-09-20"
# ⚠⚠ THE BUDGET IS PER MODE, because the two modes send prompts an order of
# magnitude apart. A single-passage call is ~1,300 tokens in; a batch call is
# 5,533 median and up to 12,121, and it asks for 15 grades instead of one.
# Measured: the 8B already timed out at 300s on a batch call.
# ⚠ One number for both was a real defect, not a tuning miss. 180s came from
# SINGLE-passage timings and was then applied to 26B BATCH calls, which failed
# the LARGEST tasks first -- so the run was quietly selecting which passages got
# graded, and packaging (the corpus that scored worst in the audit) was dropping
# out. **A timeout that fails the big cases biases the sample rather than just
# slowing it.**
CALL_TIMEOUT = {"single": 180, "batch": 1200}
# ⚠ A rate-limited provider consumes attempts WAITING, not failing, so a
# budget of 2 that suffices for a local host starves on a hosted one.
RETRIES = int(os.environ.get("A6_VALIDATE_RETRIES", "4"))


def _ckpt_path(model: str, mode: str) -> Path:
    """One checkpoint per (model, mode), so two candidates never share a file."""
    safe = model.replace(":", "-").replace("/", "-")
    d = ROOT / "validate"
    d.mkdir(exist_ok=True)
    return d / f"{safe}.{mode}.jsonl"


def _load_ckpt(path: Path) -> dict[tuple[str, str, str], int]:
    # ⚠⚠ Predictions were held in MEMORY only, so closing the laptop threw away
    # every call already paid for -- 3.2 hours of a grader's time to a lid.
    # Appended as they arrive, one JSON object per line: a half-written final line
    # is skipped rather than poisoning a resume.
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        out[(r["corpus"], r["qid"], r["section_id"])] = int(r["grade"])
    return out

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


def select_provider(name: str) -> None:
    """Point the shared `call()` at another provider for this process only.

    ⚠ `call()` reads a module-level ENDPOINT and key_env, so a candidate on a
    different host needs those rebound. Nothing is written back to disk and the
    drafting default is unaffected; the checkpoint filename carries the model, so
    two providers can never share one.
    """
    if name not in PROVIDERS:
        raise SystemExit(f"unknown provider {name!r}; have {sorted(PROVIDERS)}")
    a6_draft.PROVIDER = name
    a6_draft.ENDPOINT = PROVIDERS[name]["endpoint"]


def run(model: str, mode: str, limit: int = 0) -> None:
    g = gold()
    want: dict[tuple[str, str], set[str]] = {}
    for (corpus, qid, sec) in g:
        want.setdefault((corpus, qid), set()).add(sec)
    tasks = sorted(want)
    if limit:
        tasks = tasks[:limit]
    print(f"grader {model!r} @ {a6_draft.PROVIDER} | mode {mode} | {len(tasks)} queries "
          f"covering {sum(len(want[t]) for t in tasks)} audited passages")

    ck = _ckpt_path(model, mode)
    pred: dict[tuple[str, str, str], int] = _load_ckpt(ck)
    if pred:
        print(f"resuming from {ck.name}: {len(pred)} passages already graded")
    # ⚠⚠ A LOCK, because "resumable" invites exactly one process too many. On
    # 2026-09-22 two copies of this run appended to the same checkpoint: each
    # loaded the same 119 predictions, each skipped the same items, and both
    # graded the rest. 231 lines held 191 distinct passages. The duplicates were
    # harmless -- they collapse on load, and temperature 0 gives the same grade --
    # but ~40 passages were paid for twice on a host where a call costs 30-150s.
    lock = ck.with_suffix(".lock")
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise SystemExit(
            f"{lock.name} exists: another run is already grading {model} in {mode} "
            f"mode. If no process is running, delete it and start again.")
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    atexit.register(lambda: lock.unlink(missing_ok=True))
    fh_ck = ck.open("a", encoding="utf-8")

    def record(corpus: str, qid: str, sec: str, v: int) -> None:
        pred[(corpus, qid, sec)] = v
        fh_ck.write(json.dumps({"corpus": corpus, "qid": qid,
                                "section_id": sec, "grade": v}) + "\n")
        fh_ck.flush()

    bad = 0
    for n, (corpus, qid) in enumerate(tasks, 1):
        d = ROOT / "label_tasks" / corpus
        keymap = json.loads((d / "keymap.json").read_text(encoding="utf-8"))[qid]
        head, blocks = _task_parts((d / f"{qid}.md").read_text(encoding="utf-8"))
        need = {k: s for k, s in keymap.items()
                if s in want[(corpus, qid)] and (corpus, qid, s) not in pred}
        if not need:
            continue
        try:
            if mode == "batch":
                # Production shape: every sibling visible in one prompt.
                out, _, _ = draft_call((d / f"{qid}.md").read_text(encoding="utf-8"),
                                       model=model, retries=RETRIES, timeout=CALL_TIMEOUT[mode])
                got = out.get("grades", out)
                for k, sec in need.items():
                    cell = got.get(k)
                    v = cell.get("g") if isinstance(cell, dict) else cell
                    if v in (0, 1, 2):
                        record(corpus, qid, sec, int(v))
                    else:
                        bad += 1
            else:
                # ⚠ One passage per call. The passage is relabelled c01 so the
                # model cannot infer a position, and no sibling is present.
                for k, sec in need.items():
                    prompt = f"{head}\n\n# Passages\n\n## c01\n\n{blocks[k]}\n"
                    out, _, _ = draft_call(prompt, model=model, retries=RETRIES,
                                           timeout=CALL_TIMEOUT[mode])
                    got = out.get("grades", out)
                    cell = got.get("c01", got.get(k))
                    v = cell.get("g") if isinstance(cell, dict) else cell
                    if v in (0, 1, 2):
                        record(corpus, qid, sec, int(v))
                    else:
                        bad += 1
        except SystemExit as e:
            print(f"  FAILED {corpus}/{qid}: {e}", flush=True)
            bad += len(need)
        if n % 20 == 0:
            print(f"  {n}/{len(tasks)} queries, {len(pred)} graded", flush=True)

    fh_ck.close()
    pairs = [(pred[k], g[k]) for k in pred if k in g]
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
    ap.add_argument("--provider", default="ollama", help="ollama, groq, openai")
    ap.add_argument("--limit", type=int, default=0, help="queries, for a smoke run")
    a = ap.parse_args(argv)
    select_provider(a.provider)
    run(a.model, a.mode, a.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
