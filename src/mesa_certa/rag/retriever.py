"""Busca semântica com limiar, orçamento de contexto e citação (SDD §6.4 e §6.5)."""

from dataclasses import dataclass, replace

from mesa_certa.rag.chunker import CITATION_SEPARATOR, PATH_SEPARATOR
from mesa_certa.rag.embedder import TextEmbedder
from mesa_certa.rag.store import ChunkStore


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    content: str
    source: str
    section_path: str
    score: float  # similaridade de cosseno, 0 a 1

    @property
    def section_label(self) -> str:
        return self.section_path.replace(PATH_SEPARATOR, CITATION_SEPARATOR)

    @property
    def citation(self) -> str:
        return f"{self.source}{CITATION_SEPARATOR}{self.section_label}"


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    chunks: list[RetrievedChunk]
    below_threshold: bool

    def format_for_model(self) -> str:
        return "\n\n".join(
            f"[{index}] {chunk.citation} (relevância {chunk.score:.2f})\n{chunk.content}"
            for index, chunk in enumerate(self.chunks, start=1)
        )


class Retriever:
    def __init__(
        self,
        embedder: TextEmbedder,
        store: ChunkStore,
        top_k: int = 4,
        similarity_threshold: float = 0.85,
        max_context_chars: int = 4000,
    ) -> None:
        self._embedder = embedder
        self._store = store
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self.max_context_chars = max_context_chars

    def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        """Ranking bruto, sem limiar nem orçamento. Base das métricas de recuperação."""
        matches = self._store.query(self._embedder.embed_query(query), top_k or self.top_k)
        return [
            RetrievedChunk(
                chunk_id=match.chunk_id,
                content=match.content,
                source=str(match.metadata.get("source", "")),
                section_path=str(match.metadata.get("section_path", "")),
                score=min(1.0, max(0.0, 1.0 - match.distance)),
            )
            for match in matches
        ]

    def retrieve(self, query: str, top_k: int | None = None) -> RetrievalResult:
        passing = [c for c in self.search(query, top_k) if c.score >= self.similarity_threshold]
        return RetrievalResult(
            query=query,
            chunks=self._fit_budget(passing),
            below_threshold=not passing,
        )

    def _fit_budget(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        selected: list[RetrievedChunk] = []
        used = 0
        for chunk in chunks:
            remaining = self.max_context_chars - used
            if len(chunk.content) > remaining:
                if selected:
                    break
                chunk = replace(chunk, content=chunk.content[:remaining])
            selected.append(chunk)
            used += len(chunk.content)
        return selected
