"""Dublês de teste compartilhados."""

import hashlib
import math
import re
import unicodedata
from collections.abc import Sequence

from mesa_certa.rag.embedder import QUERY_PREFIX

DIMENSIONS = 384
_WORD = re.compile(r"[a-z0-9]+")


class HashingEmbedder:
    """Bag of words com hashing: determinístico, sem rede, similaridade por palavras em comum."""

    def __init__(self) -> None:
        self.query_calls: list[str] = []
        self.passage_calls: list[list[str]] = []

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return self._vector(text)

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        self.passage_calls.append(list(texts))
        return [self._vector(t) for t in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
        vector = [0.0] * DIMENSIONS
        for word in _WORD.findall(folded):
            index = int(hashlib.md5(word.encode()).hexdigest(), 16) % DIMENSIONS
            vector[index] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class RecordingModel:
    """Imita `SentenceTransformer.encode` e guarda o que recebeu."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def encode(self, sentences: list[str], **kwargs: object) -> list[list[float]]:
        self.calls.append((list(sentences), kwargs))
        return [[1.0 if s.startswith(QUERY_PREFIX) else 0.0, 1.0] for s in sentences]
