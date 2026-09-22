"""The review harness must never be able to see the answers.

⚠⚠ The audit pack's blindness is the only thing that makes its agreement rate
mean anything. A review tool that opened `<name>.key.json` -- to pre-fill, to
"check", to order items by difficulty -- would destroy the measurement while
leaving the CSV looking exactly as it should. Nothing in the output would show
it, which is why this is a source-level ratchet and not a behavioural test.
"""

from __future__ import annotations

import ast
from pathlib import Path

MODULE = Path(__file__).resolve().parent.parent / "bench" / "audit_review.py"


def _string_constants_excluding_docstrings(tree: ast.AST) -> list[str]:
    """Every string literal in the module except the doc comments."""
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None and node.body and isinstance(node.body[0], ast.Expr):
                docstrings.add(id(node.body[0].value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            out.append(node.value)
    return out


def test_review_module_never_names_the_key_file() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    hits = [s for s in _string_constants_excluding_docstrings(tree) if "key" in s.lower()]
    assert hits == [], f"review harness references the answer key in code: {hits}"


def test_the_only_key_json_mention_is_the_promise_not_to_read_it() -> None:
    # ⚠ The docstring SAYS it never opens the key. If that sentence is ever
    # deleted, this test fails too -- the promise and the guard travel together.
    text = MODULE.read_text(encoding="utf-8")
    assert "key.json" in text, "the blindness promise was removed from the docstring"
    tree = ast.parse(text)
    assert not [s for s in _string_constants_excluding_docstrings(tree) if "key.json" in s]


def test_review_reads_only_the_blind_pair() -> None:
    """The file suffixes this module builds are the .md and the .csv, nothing else.

    An f-string is a JoinedStr, so the literal half of `f"{name}.md"` is ".md" --
    reading it as one constant is how a guard like this quietly matches nothing.
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    suffixes = {s for s in _string_constants_excluding_docstrings(tree)
                if s.startswith(".") and len(s) <= 6}
    assert suffixes == {".md", ".csv"}, suffixes
