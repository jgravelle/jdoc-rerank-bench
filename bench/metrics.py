"""Graded ranking metrics + paired bootstrap.

jdocmunch's benchmarks/replay/metrics.py is binary-gain; BENCH-004 labels are
graded (0/1/2), so nDCG here uses 2**grade - 1 and an ideal ordering built from
every labeled passage for the query, not only the ones an arm surfaced.
"""

from __future__ import annotations

import math
import random
from typing import Callable, Mapping, Sequence

Labels = Mapping[str, int]  # section_id -> grade; absent means 0


def _gain(grade: int) -> float:
    return float(2 ** grade - 1)


def dcg(grades: Sequence[int]) -> float:
    return sum(_gain(g) / math.log2(i + 2) for i, g in enumerate(grades))


def ndcg_at_k(ranked: Sequence[str], labels: Labels, k: int) -> float:
    ideal = dcg(sorted(labels.values(), reverse=True)[:k])
    if ideal == 0:
        return 0.0
    return dcg([labels.get(s, 0) for s in ranked[:k]]) / ideal


def precision_at_k(ranked: Sequence[str], labels: Labels, k: int, min_grade: int = 1) -> float:
    if k <= 0:
        return 0.0
    return sum(1 for s in ranked[:k] if labels.get(s, 0) >= min_grade) / k


def mrr(ranked: Sequence[str], labels: Labels, k: int, min_grade: int = 1) -> float:
    for i, s in enumerate(ranked[:k]):
        if labels.get(s, 0) >= min_grade:
            return 1.0 / (i + 1)
    return 0.0


def recall_at_k(ranked: Sequence[str], labels: Labels, k: int, min_grade: int = 1) -> float:
    relevant = {s for s, g in labels.items() if g >= min_grade}
    if not relevant:
        return 0.0
    return len(relevant & set(ranked[:k])) / len(relevant)


def oracle_order(pool: Sequence[str], labels: Labels) -> list[str]:
    """Arm O: the pool sorted by grade, original rank as the tiebreak."""
    return [s for _, s in sorted(enumerate(pool), key=lambda t: (-labels.get(t[1], 0), t[0]))]


def bootstrap_ci(
    values: Sequence[float],
    *,
    iters: int = 10_000,
    alpha: float = 0.05,
    seed: int = 0,
    stat: Callable[[Sequence[float]], float] = lambda v: sum(v) / len(v),
) -> tuple[float, float, float]:
    """(point, lo, hi) over queries. For a paired difference pass per-query
    deltas — resampling the two arms independently would discard the pairing."""
    if not values:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    stats = sorted(stat([values[rng.randrange(n)] for _ in range(n)]) for _ in range(iters))
    lo = stats[int((alpha / 2) * iters)]
    hi = stats[min(iters - 1, int((1 - alpha / 2) * iters))]
    return (stat(values), lo, hi)
