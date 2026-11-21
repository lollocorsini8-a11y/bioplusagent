"""
Embedding locale a feature-hashing (nessun download, nessuna rete).
Va bene per la demo e per un corpus piccolo. Per produzione sostituisci `embed()`
con un modello vero (es. sentence-transformers multilingue) mantenendo EMB_DIM.
"""
from __future__ import annotations

import hashlib
import math
import re

EMB_DIM = 256
_TOKEN = re.compile(r"[a-zàèéìòù0-9]+", re.IGNORECASE)


def _tokens(text: str) -> list[str]:
    words = [w.lower() for w in _TOKEN.findall(text) if len(w) > 2]
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:])]


def embed(text: str) -> list[float]:
    vec = [0.0] * EMB_DIM
    for tok in _tokens(text):
        h = int.from_bytes(hashlib.md5(tok.encode()).digest()[:8], "big")
        vec[h % EMB_DIM] += 1.0 if (h >> 63) & 1 else -1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
