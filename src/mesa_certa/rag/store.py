"""Cliente do ChromaDB em disco (ADR-004).

A collection não tem função de embedding própria: os vetores vêm sempre do `Embedder`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

MetadataValue = str | int | float | bool | None


@dataclass(frozen=True)
class StoredMatch:
    chunk_id: str
    content: str
    metadata: Mapping[str, MetadataValue]
    distance: float


class ChunkStore:
    def __init__(self, path: Path, collection_name: str) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,
        )

    def count(self) -> int:
        return self._collection.count()

    def hashes(self) -> dict[str, str]:
        result = self._collection.get(include=["metadatas"])
        metadatas = result["metadatas"] or []
        return {
            chunk_id: str(meta.get("content_hash", ""))
            for chunk_id, meta in zip(result["ids"], metadatas, strict=True)
        }

    def upsert(
        self,
        ids: Sequence[str],
        documents: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[Mapping[str, MetadataValue]],
    ) -> None:
        vectors: list[Sequence[float] | Sequence[int]] = [list(e) for e in embeddings]
        self._collection.upsert(
            ids=list(ids),
            documents=list(documents),
            embeddings=vectors,
            metadatas=[dict(m) for m in metadatas],
        )

    def delete(self, ids: Sequence[str]) -> None:
        self._collection.delete(ids=list(ids))

    def query(self, embedding: Sequence[float], n_results: int) -> list[StoredMatch]:
        available = self.count()
        if available == 0 or n_results <= 0:
            return []
        query_vectors: list[Sequence[float] | Sequence[int]] = [list(embedding)]
        result: Any = self._collection.query(
            query_embeddings=query_vectors,
            n_results=min(n_results, available),
            include=["documents", "metadatas", "distances"],
        )
        return [
            StoredMatch(chunk_id, document or "", metadata or {}, float(distance))
            for chunk_id, document, metadata, distance in zip(
                result["ids"][0],
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
                strict=True,
            )
        ]
