"""Rerank providers. One interface (SEM-010): score(query, candidates) -> {id: float}.

Scores are ordinal evidence only. Nothing downstream treats them as calibrated.
"""

from __future__ import annotations

import math
from typing import Protocol


def passage_text(c: dict, metadata: bool = True) -> str:
    head = " > ".join((c.get("heading_path") or [])[1:]) if metadata else ""
    return f"{head}\n\n{c['body']}".strip()


class Provider(Protocol):
    name: str
    version: str

    def score(self, query: str, candidates: dict[str, dict]) -> dict[str, float]: ...


class Answerability:
    """Arm A': the heuristic jdocmunch already attaches to every row. Free."""
    name, version = "answerability", "jdocmunch-row"

    def score(self, query, candidates):
        return {sid: float(c.get("answerability") or 0.0) for sid, c in candidates.items()}


class CrossEncoder:
    """Arm C: a small open cross-encoder, fully local."""
    name = "cross-encoder"

    def __init__(self, model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", device: str = "cpu"):
        from sentence_transformers import CrossEncoder as _CE
        self.version = model
        # CPU on purpose: the latency a user without a GPU would see.
        self._m = _CE(model, max_length=512, device=device)

    def score(self, query, candidates):
        ids = list(candidates)
        raw = self._m.predict([(query, passage_text(candidates[i])) for i in ids])
        return {i: 1.0 / (1.0 + math.exp(-float(x))) for i, x in zip(ids, raw)}


class OnnxCrossEncoder:
    """Arm C as it would ship: ONNX via fastembed, no torch."""
    name = "onnx-cross-encoder"

    def __init__(self, model: str = "Xenova/ms-marco-MiniLM-L-6-v2"):
        import time
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        t0 = time.perf_counter()
        self._m = TextCrossEncoder(model_name=model)
        self.load_ms = round((time.perf_counter() - t0) * 1000, 1)
        self.version = model

    def score(self, query, candidates):
        ids = list(candidates)
        raw = list(self._m.rerank(query, [passage_text(candidates[i]) for i in ids]))
        return {i: 1.0 / (1.0 + math.exp(-float(x))) for i, x in zip(ids, raw)}


class OnnxInt8:
    """The pre-registered config (DECISION_CRITERIA.md section 4 + amendment A1):
    int8 weights, 512 tokens, one passage per inference call, 4 threads."""
    name = "onnx-int8-b1"
    version = "Xenova/ms-marco-MiniLM-L-6-v2:model_quantized:512:b1:t4"

    def __init__(self):
        from .levers import Ort
        self._m = Ort("int8", 512, threads=4)
        self._m.bucket = 1

    def score(self, query, candidates):
        ids = list(candidates)
        raw = self._m.score(query, [passage_text(candidates[i]) for i in ids])
        return {i: 1.0 / (1.0 + math.exp(-x)) for i, x in zip(ids, raw)}


REGISTRY = {"onnx-int8-b1": OnnxInt8, "onnx-cross-encoder": OnnxCrossEncoder, "answerability": Answerability, "cross-encoder": CrossEncoder}
