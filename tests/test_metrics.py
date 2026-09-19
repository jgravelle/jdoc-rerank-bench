from bench.metrics import bootstrap_ci, mrr, ndcg_at_k, oracle_order, precision_at_k, recall_at_k
from bench.pools import cap_body

LABELS = {"a": 2, "b": 1, "c": 0, "d": 2}


def test_ndcg_perfect_and_worst():
    assert ndcg_at_k(["a", "d", "b"], LABELS, 3) == 1.0
    assert ndcg_at_k(["c", "x", "y"], LABELS, 3) == 0.0


def test_ndcg_ideal_counts_unsurfaced_relevant():
    # "d" (grade 2) was never returned; the arm must not score 1.0 without it.
    assert ndcg_at_k(["a", "b"], LABELS, 3) < 1.0


def test_ndcg_graded_order_matters():
    assert ndcg_at_k(["a", "b"], LABELS, 2) > ndcg_at_k(["b", "a"], LABELS, 2)


def test_ndcg_no_relevant_is_zero():
    assert ndcg_at_k(["a"], {"a": 0}, 5) == 0.0


def test_p_mrr_recall():
    assert precision_at_k(["c", "a"], LABELS, 1) == 0.0
    assert mrr(["c", "a"], LABELS, 5) == 0.5
    assert recall_at_k(["a", "b"], LABELS, 2) == 2 / 3
    assert recall_at_k(["a", "b"], LABELS, 2, min_grade=2) == 0.5


def test_oracle_is_stable_on_ties():
    assert oracle_order(["c", "b", "d", "a"], LABELS) == ["d", "a", "b", "c"]


def test_bootstrap_deterministic_and_brackets_point():
    vals = [0.1, -0.05, 0.2, 0.0, 0.15, 0.05]
    a = bootstrap_ci(vals, iters=2000, seed=1)
    assert a == bootstrap_ci(vals, iters=2000, seed=1)
    assert a[1] <= a[0] <= a[2]


def test_cap_body_cuts_at_paragraph():
    text = "x" * 4000 + "\n\n" + "y" * 4000
    assert cap_body(text) == "x" * 4000
    assert cap_body("short") == "short"
