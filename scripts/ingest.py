"""Indexa data/knowledge no ChromaDB de forma idempotente. Alvo `make ingest`."""

from zoneinfo import ZoneInfo

from mesa_certa.config import get_settings
from mesa_certa.domain.date_resolver import SystemClock
from mesa_certa.rag.embedder import Embedder
from mesa_certa.rag.ingest import ingest_directory
from mesa_certa.rag.store import ChunkStore


def main() -> None:
    settings = get_settings()
    store = ChunkStore(settings.chroma_path, settings.chroma_collection)
    report = ingest_directory(
        settings.knowledge_path,
        Embedder(settings.embedding_model),
        store,
        SystemClock(ZoneInfo(settings.timezone)),
    )
    print(f"Ingestão concluída. {report.summary()}. Total no índice: {store.count()}")


if __name__ == "__main__":
    main()
