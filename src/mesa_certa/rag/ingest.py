"""Ingestão idempotente (SDD §6.3, RF-10).

Compara por `chunk_id` e `content_hash`: só recalcula embedding do que mudou e remove do
índice o que sumiu dos documentos. Sem mudança, nenhuma escrita.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from mesa_certa.domain.date_resolver import Clock
from mesa_certa.rag.chunker import Chunk, chunk_directory
from mesa_certa.rag.embedder import TextEmbedder
from mesa_certa.rag.store import ChunkStore, MetadataValue


@dataclass(frozen=True)
class IngestReport:
    created: tuple[str, ...]
    updated: tuple[str, ...]
    removed: tuple[str, ...]
    unchanged: tuple[str, ...]

    @property
    def writes(self) -> int:
        return len(self.created) + len(self.updated) + len(self.removed)

    def summary(self) -> str:
        return (
            f"criados: {len(self.created)}, atualizados: {len(self.updated)}, "
            f"removidos: {len(self.removed)}, inalterados: {len(self.unchanged)}"
        )


def chunk_metadata(chunk: Chunk, indexed_at: str) -> dict[str, MetadataValue]:
    return {
        "source": chunk.source,
        "doc_title": chunk.doc_title,
        "section_path": chunk.section_path,
        "chunk_id": chunk.chunk_id,
        "content_hash": chunk.content_hash,
        "char_count": chunk.char_count,
        "indexed_at": indexed_at,
    }


def ingest(
    chunks: Sequence[Chunk], embedder: TextEmbedder, store: ChunkStore, clock: Clock
) -> IngestReport:
    existing = store.hashes()
    current_ids = {c.chunk_id for c in chunks}

    to_write = [c for c in chunks if existing.get(c.chunk_id) != c.content_hash]
    written_ids = {c.chunk_id for c in to_write}
    report = IngestReport(
        created=tuple(c.chunk_id for c in to_write if c.chunk_id not in existing),
        updated=tuple(c.chunk_id for c in to_write if c.chunk_id in existing),
        removed=tuple(sorted(set(existing) - current_ids)),
        unchanged=tuple(c.chunk_id for c in chunks if c.chunk_id not in written_ids),
    )

    if to_write:
        indexed_at = clock.now().isoformat(timespec="seconds")
        store.upsert(
            ids=[c.chunk_id for c in to_write],
            documents=[c.content for c in to_write],
            embeddings=embedder.embed_passages([c.text for c in to_write]),
            metadatas=[chunk_metadata(c, indexed_at) for c in to_write],
        )
    if report.removed:
        store.delete(report.removed)
    return report


def ingest_directory(
    knowledge_path: Path, embedder: TextEmbedder, store: ChunkStore, clock: Clock
) -> IngestReport:
    return ingest(chunk_directory(knowledge_path), embedder, store, clock)
