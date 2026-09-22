"""Interactive front-end for the human audit sheet (BENCH-006, A6 section 7).

⚠⚠ This is a HARNESS, not an auditor. Section 7 makes the auditor a human and
records that A1's second-model audit does not carry over, so nothing in this
module forms, suggests, defaults or infers a grade. It renders one item, takes
what the person types, and records it.

⚠⚠ It NEVER opens `<name>.key.json`. The pack's blindness is the only thing that
makes its agreement rate mean anything, and a tool that peeked in order to
"help" would destroy the measurement while leaving the CSV looking normal.
`tests/test_audit_review_is_blind.py` walks this module's AST for the string.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEM_RE = re.compile(r"^## (A\d+)$(.*?)(?=^---$|\Z)", re.M | re.S)
VALID = ("0", "1", "2")


def _load_items(md: str) -> dict[str, str]:
    return {m.group(1): m.group(2).strip() for m in ITEM_RE.finditer(md)}


def _graded(rows: list[dict]) -> int:
    return sum(1 for r in rows if r["human_grade"].strip() in VALID)


def review(name: str, start: str = "", limit: int = 0) -> None:
    out = ROOT / "audit"
    items = _load_items((out / f"{name}.md").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((out / f"{name}.csv").open(encoding="utf-8")))

    def save() -> None:
        with (out / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["item", "human_grade", "note"])
            for r in rows:
                w.writerow([r["item"], r["human_grade"], r["note"]])

    todo = [r for r in rows if r["human_grade"].strip() not in VALID]
    if start:
        todo = [r for r in todo if r["item"] >= start]
    if limit:
        todo = todo[:limit]

    print(f"{name}: {_graded(rows)} of {len(rows)} graded already; "
          f"{len(todo)} queued this sitting.")
    print("Grade 0, 1 or 2. Enter alone skips an item. 'q' saves and quits.")
    print("The note is optional.")

    for i, row in enumerate(todo, 1):
        print()
        print("=" * 72)
        print(f"[{i}/{len(todo)}]  {row['item']}")
        print("=" * 72)
        print(items.get(row["item"], "(no item text found in the .md)"))
        print("-" * 72)
        while True:
            try:
                g = input(f"{row['item']} grade [0/1/2, Enter=skip, q=quit]: ").strip().lower()
            except EOFError:
                g = "q"
            if g == "q":
                save()
                print(f"\nSaved. {_graded(rows)} of {len(rows)} graded.")
                return
            if g == "":
                break
            if g in VALID:
                try:
                    note = input("  note (optional): ").strip()
                except EOFError:
                    note = ""
                row["human_grade"], row["note"] = g, note
                # ⚠ Save after EVERY grade. 440 items is many sittings, and an
                # hour of judgement lost to a closed terminal is paid for in the
                # one currency this audit cannot mint more of.
                save()
                break
            print("  Enter 0, 1, 2, nothing, or q.")

    save()
    print(f"\nSitting over. {_graded(rows)} of {len(rows)} graded.")
    if _graded(rows) == len(rows):
        print(f"Sheet complete. Now run:  python -m bench.audit agree --name {name}")
