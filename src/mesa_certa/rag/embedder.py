"""Embeddings e5 com os prefixos exigidos pelo modelo (ADR-003).

O e5 foi treinado com `query: ` nas perguntas e `passage: ` nos documentos. Esquecer o
prefixo degrada a recuperação sem erro visível, por isso ele fica encapsulado aqui.
"""

from collections.abc import Sequence
from typing import Any, Protocol

QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "


class TextEmbedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]: ...


class Embedder:
    def __init__(self, model_name: str, model: Any | None = None, device: str = "cpu") -> None:
        self._model_name = model_name
        self._model = model
        self._device = device

    @property
    def model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name, device=self._device)
        return self._model

    def embed_query(self, text: str) -> list[float]:
        return self._encode([QUERY_PREFIX + text])[0]

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._encode([PASSAGE_PREFIX + t for t in texts])

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [[float(value) for value in vector] for vector in vectors]
