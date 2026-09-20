r"""A6 §9 steps 6-7: freeze the reviewed drafts into A6-dev and A6-test query files.

Deterministic. No randomness, no seed, no retrieval, no reranker, no Jev score.
Re-running it on the same drafts writes byte-identical files.

Allocation, in this order:

  1. Q4 and Q5 test quotas are spread across corpora by largest remainder over
     what each corpus HAS, capped by availability.
  2. Q4 and Q5 dev quotas are spread the same way over what each corpus has LEFT.
  3. Q3 is the equalizer: its per-corpus quota is whatever it takes to bring each
     corpus to the same ranking mass. ⚠ This is why Q3 is allocated LAST — a
     proportional Q3 draw gave 33/46/47/35 per corpus in test, and section 2 asks
     for roughly even Q3-Q5 mass.
  4. Q6 controls and Q2 literals go to test only, spread evenly. Section 2's dev
     table names Q3/Q4/Q5 and nothing else, so dev carries no controls.

⚠⚠ Within one (corpus, class) stratum, rows are sorted by (-so_score, qid) and
then dealt to test and dev by a fractional accumulator, NOT split at a cut point.
A cut would give test the high-vote half and dev the low-vote half, so the grid
picked on dev would be tuned on a systematically easier or harder distribution
than the one it is applied to. Both splits get the same score spread.

Surplus rows stay in `queries/_draft/` unassigned. Nothing is deleted.

    python -m bench.a6_freeze            # write the files
    python -m bench.a6_freeze --check    # report only, write nothing
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

from .a6_queries import ROOT, jaccard, norm, source_id, toks

CORPORA = ["packaging", "pytest", "fastapi", "django"]

# results/LABEL-DESIGN-A6.md section 2. Targets, not minima; the floors are
# asserted separately in `check_floors` so a quota edit cannot lower a floor.
TEST_QUOTA = {"Q3": 90, "Q4": 35, "Q5": 35, "Q6": 20, "Q2": 18}
DEV_QUOTA = {"Q3": 40, "Q4": 20, "Q5": 20}

# Section 2's "honest minimum" column.
TEST_FLOOR = {"Q3": 30, "Q4": 30, "Q5": 30, "Q6": 10, "Q2": 15}
TEST_RANKING_FLOOR = 150
DEV_FLOOR = {"Q3": 12, "Q4": 12, "Q5": 12}
DEV_RANKING_FLOOR = 60
DEV_RANKING_TARGET = 80  # under this, record as underpowered


def largest_remainder(total: int, avail: dict[str, int]) -> dict[str, int]:
    """Spread `total` over corpora proportionally to `avail`, capped by it."""
    pool = sum(avail.values())
    if total > pool:
        raise ValueError(f"need {total}, only {pool} available: {avail}")
    exact = {c: total * avail[c] / pool for c in avail}
    out = {c: min(int(exact[c]), avail[c]) for c in avail}
    # Hand out what rounding left, highest fractional part first, then by name
    # so the result does not depend on dict order.
    order = sorted(avail, key=lambda c: (-(exact[c] - int(exact[c])), c))
    while sum(out.values()) < total:
        moved = False
        for c in order:
            if out[c] < avail[c]:
                out[c] += 1
                moved = True
                if sum(out.values()) == total:
                    break
        if not moved:
            raise ValueError(f"cannot reach {total} under caps {avail}")
    return out


def deal(rows: list[dict], n_test: int, n_dev: int) -> tuple[list[dict], list[dict]]:
    """Interleave one stratum into test and dev across its whole score range."""
    test, dev = [], []
    want = n_test + n_dev
    if want == 0:
        return test, dev
    acc = 0.0
    for row in rows[:want]:
        # acc tracks the test share owed so far; whoever is furthest behind takes
        # the next row. Deterministic for any (n_test, n_dev).
        if n_test and (not n_dev or acc + 1e-9 < n_test / want * (len(test) + len(dev) + 1)):
            test.append(row)
        elif n_dev and len(dev) < n_dev:
            dev.append(row)
        else:
            test.append(row)
        acc = len(test)
    return test[:n_test], dev[:n_dev]


def load_drafts(spent_sources: set[str]) -> tuple[dict[str, list[dict]], list[dict]]:
    """Reviewed drafts, grouped by corpus, minus every row whose SOURCE is spent.

    ⚠⚠ The drafts are the RAW record and are not edited; the exclusion happens
    here, on every run, and every excluded row is printed with what it collides
    with. A silent drop would leave the count in `results/a6-class-review.md`
    disagreeing with the frozen files for a reason nobody could reconstruct.
    """
    by_corpus: dict[str, list[dict]] = {c: [] for c in CORPORA}
    excluded: list[dict] = []
    for path in sorted((ROOT / "queries" / "_draft").glob("a6-batch*.jsonl")):
        corpus = path.stem.rsplit("-", 1)[1]
        if corpus not in by_corpus:
            raise ValueError(f"{path.name}: unknown corpus {corpus!r}")
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            row["corpus"] = corpus
            sid = source_id(row)
            if sid and sid in spent_sources:
                row["_excluded"] = f"source question {sid} already frozen"
                excluded.append(row)
                continue
            by_corpus[corpus].append(row)
    return by_corpus, excluded


def spent_excluding_drafts() -> tuple[set[str], list[set[str]], set[str]]:
    """Everything already committed to a FROZEN split or a label file.

    ⚠ `a6_queries.spent()` globs `queries/**`, which INCLUDES `queries/_draft/`, so
    the drafts count themselves and every row reads as a reuse. This is the same
    three channels over the frozen corpus only.
    """
    qids: set[str] = set()
    texts: set[str] = set()
    sources: set[str] = set()
    a6 = tuple(f"{c}-a6" for c in CORPORA)
    for p in list(ROOT.glob("queries/**/*.jsonl")) + list(ROOT.glob("labels/**/*.jsonl")):
        if "_draft" in p.parts or p.name.startswith(a6):
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if "qid" in r:
                    qids.add(r["qid"])
                if r.get("query"):
                    texts.add(norm(r["query"]))
                sid = source_id(r)
                if sid:
                    sources.add(sid)
    return qids, [toks(t) for t in texts], sources


def check_floors(counts: dict[str, collections.Counter]) -> list[str]:
    fails = []
    t, d = counts["test"], counts["dev"]
    for cls, floor in TEST_FLOOR.items():
        if t[cls] < floor:
            fails.append(f"test {cls} {t[cls]} < floor {floor}")
    ranking_t = sum(t[c] for c in ("Q3", "Q4", "Q5"))
    if ranking_t < TEST_RANKING_FLOOR:
        fails.append(f"test Q3-Q5 pooled {ranking_t} < floor {TEST_RANKING_FLOOR}")
    for cls, floor in DEV_FLOOR.items():
        if d[cls] < floor:
            fails.append(f"dev {cls} {d[cls]} < floor {floor}")
    ranking_d = sum(d[c] for c in ("Q3", "Q4", "Q5"))
    if ranking_d < DEV_RANKING_FLOOR:
        fails.append(f"dev Q3-Q5 pooled {ranking_d} < floor {DEV_RANKING_FLOOR}")
    return fails


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only; write nothing")
    a = ap.parse_args(argv)

    sq, st, ss = spent_excluding_drafts()
    drafts, excluded = load_drafts(ss)
    if excluded:
        by_cls = collections.Counter(r["class"] for r in excluded)
        by_corpus = collections.Counter(r["corpus"] for r in excluded)
        print(f"EXCLUDED {len(excluded)} draft rows reusing a frozen source question")
        print(f"  by class:  {dict(sorted(by_cls.items()))}")
        print(f"  by corpus: {dict(sorted(by_corpus.items()))}")
    avail = {cls: {c: sum(r["class"] == cls for r in drafts[c]) for c in CORPORA}
             for cls in ("Q2", "Q3", "Q4", "Q5", "Q6")}
    print("available per class/corpus:")
    for cls in sorted(avail):
        print(f"  {cls}: {avail[cls]}  total {sum(avail[cls].values())}")

    # Feasibility BEFORE allocation. ⚠ Without this the first unreachable quota
    # raises out of `largest_remainder`, and a traceback naming one class reads as
    # a bug in the allocator rather than as "the corpus cannot support the floors"
    # — which is step 7's STOP condition and the answer the caller needs.
    short = []
    for cls in ("Q2", "Q3", "Q4", "Q5", "Q6"):
        have = sum(avail[cls].values())
        floor = TEST_FLOOR.get(cls, 0) + DEV_FLOOR.get(cls, 0)
        target = TEST_QUOTA.get(cls, 0) + DEV_QUOTA.get(cls, 0)
        mark = "OK " if have >= target else ("FLOOR-SHORT" if have < floor else "under target")
        print(f"  {cls}: have {have:3d} | floor {floor:3d} | target {target:3d}  {mark}")
        if have < floor:
            short.append(f"{cls}: have {have}, floor is {floor} "
                         f"(test {TEST_FLOOR.get(cls, 0)} + dev {DEV_FLOOR.get(cls, 0)})")
    if short:
        print("\nREFUSED, nothing written — section 2 floors are not reachable:")
        for s in short:
            print(f"  - {s}")
        print("\nStep 7 STOP. More sourcing is needed before either split can be frozen.")
        return 1

    # 1-2. Q4/Q5 first: they are the scarce strata, so they choose, not inherit.
    quota = {"test": {}, "dev": {}}
    for cls in ("Q4", "Q5"):
        quota["test"][cls] = largest_remainder(TEST_QUOTA[cls], avail[cls])
        left = {c: avail[cls][c] - quota["test"][cls][c] for c in CORPORA}
        quota["dev"][cls] = largest_remainder(DEV_QUOTA[cls], left)

    # 3. Q3 equalizes ranking mass per corpus, as far as each corpus can supply it.
    want = {}
    for split, q in (("test", TEST_QUOTA), ("dev", DEV_QUOTA)):
        ranking_total = sum(q[c] for c in ("Q3", "Q4", "Q5"))
        base, rem = divmod(ranking_total, len(CORPORA))
        target = {c: base + (1 if i < rem else 0) for i, c in enumerate(CORPORA)}
        w = {}
        for c in CORPORA:
            already = quota[split]["Q4"][c] + quota[split]["Q5"][c]
            if target[c] - already < 0:
                raise ValueError(f"{split}/{c}: Q4+Q5 already {already} > {target[c]}")
            w[c] = target[c] - already
        want[split] = w

    # ⚠ packaging has 36 Q3 and perfect evenness asks for 37 across both splits.
    # The repair MOVES the shortfall to a corpus with spare Q3 rather than
    # shrinking the pooled Q3 total: the floors are stated on the pooled figure,
    # and a corpus one query light is a smaller distortion than a thinner split.
    # Test absorbs the move because it has slack over its floor; dev is already at
    # its target. Deterministic: most spare first, then by corpus name.
    for c in CORPORA:
        over = want["test"][c] + want["dev"][c] - avail["Q3"][c]
        while over > 0:
            if want["test"][c] == 0:
                raise ValueError(f"{c}: {over} Q3 short and test cannot give more")
            want["test"][c] -= 1
            spare = sorted(CORPORA,
                           key=lambda x: (-(avail["Q3"][x] - want["test"][x] - want["dev"][x]), x))
            for dest in spare:
                if avail["Q3"][dest] - want["test"][dest] - want["dev"][dest] > 0:
                    want["test"][dest] += 1
                    print(f"  ⚠ Q3 test: moved 1 from {c} (only {avail['Q3'][c]} available) "
                          f"to {dest}")
                    break
            else:
                raise ValueError(f"{c}: {over} Q3 short and no corpus has spare")
            over -= 1
    for split in ("test", "dev"):
        quota[split]["Q3"] = want[split]

    # 4. Controls and literals, test only, spread evenly.
    for cls in ("Q6", "Q2"):
        quota["test"][cls] = largest_remainder(TEST_QUOTA[cls],
                                              {c: avail[cls][c] for c in CORPORA})
        quota["dev"][cls] = {c: 0 for c in CORPORA}

    print("\nquotas (test / dev):")
    for cls in ("Q2", "Q3", "Q4", "Q5", "Q6"):
        print(f"  {cls}: test {quota['test'][cls]} = {sum(quota['test'][cls].values())}"
              f" | dev {quota['dev'][cls]} = {sum(quota['dev'][cls].values())}")

    # Deal each stratum.
    out: dict[str, dict[str, list[dict]]] = {"test": {c: [] for c in CORPORA},
                                             "dev": {c: [] for c in CORPORA}}
    for c in CORPORA:
        for cls in ("Q2", "Q3", "Q4", "Q5", "Q6"):
            stratum = sorted((r for r in drafts[c] if r["class"] == cls),
                             key=lambda r: (-(r.get("so_score") or 0), r["qid"]))
            t, d = deal(stratum, quota["test"][cls][c], quota["dev"][cls][c])
            out["test"][c] += t
            out["dev"][c] += d

    # Provenance checks. Every one of these has to hold before anything is written.
    all_rows = [r for s in out for c in CORPORA for r in out[s][c]]
    qids = [r["qid"] for r in all_rows]
    texts = [norm(r["query"]) for r in all_rows]
    problems = []
    if len(set(qids)) != len(qids):
        dup = [q for q, n in collections.Counter(qids).items() if n > 1]
        problems.append(f"duplicate qid across the two splits: {dup[:5]}")
    if len(set(texts)) != len(texts):
        dup = [t for t, n in collections.Counter(texts).items() if n > 1]
        problems.append(f"duplicate query text: {dup[:3]}")
    reused = sorted(set(qids) & sq)
    if reused:
        problems.append(f"{len(reused)} spent qid reused: {reused[:5]}")
    near = [r["qid"] for r in all_rows
            if any(jaccard(toks(norm(r["query"])), s) >= 0.85 for s in st)]
    if near:
        problems.append(f"{len(near)} near-duplicate of a spent query: {near[:5]}")
    resourced = [r["qid"] for r in all_rows if (source_id(r) or "") in ss]
    if resourced:
        problems.append(f"{len(resourced)} spent SOURCE question reused: {resourced[:5]}")
    dev_ids = {r["qid"] for s in ["dev"] for c in CORPORA for r in out[s][c]}
    test_ids = {r["qid"] for c in CORPORA for r in out["test"][c]}
    if dev_ids & test_ids:
        problems.append(f"dev and test overlap: {sorted(dev_ids & test_ids)[:5]}")

    counts = {s: collections.Counter(r["class"] for c in CORPORA for r in out[s][c])
              for s in ("test", "dev")}
    problems += check_floors(counts)

    print("\nfinal counts:")
    for s in ("test", "dev"):
        ranking = sum(counts[s][c] for c in ("Q3", "Q4", "Q5"))
        print(f"  A6-{s}: {dict(sorted(counts[s].items()))} "
              f"| Q3-Q5 pooled {ranking} | total {sum(counts[s].values())}")
        for c in CORPORA:
            cc = collections.Counter(r["class"] for r in out[s][c])
            rank_c = sum(cc[k] for k in ("Q3", "Q4", "Q5"))
            print(f"    {c}: {dict(sorted(cc.items()))} | ranking {rank_c}")
    dev_ranking = sum(counts["dev"][c] for c in ("Q3", "Q4", "Q5"))
    if dev_ranking < DEV_RANKING_TARGET:
        print(f"⚠ dev Q3-Q5 pooled {dev_ranking} < target {DEV_RANKING_TARGET}: "
              f"record A6-dev as UNDERPOWERED")

    if problems:
        print("\nREFUSED, nothing written:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nall floors and provenance checks pass")

    if a.check:
        print("--check: nothing written")
        return 0

    fields = ["qid", "class", "query", "source", "so_score", "so_tags", "corpus", "split"]
    for s in ("test", "dev"):
        for c in CORPORA:
            rows = sorted(out[s][c], key=lambda r: (r["class"], r["qid"]))
            for r in rows:
                r["split"] = f"a6{s}"
            dest = ROOT / "queries" / f"{c}-a6{s}.jsonl"
            dest.write_text(
                "\n".join(json.dumps({k: r[k] for k in fields if k in r}) for r in rows)
                + "\n", encoding="utf-8")
            print(f"wrote {len(rows):3d} -> {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
