"""Prepara banco e índice antes da API subir. Idempotente: pode rodar a cada partida.

Migra sempre, semeia só se o banco estiver vazio e reindexa só o que mudou.
"""

from pathlib import Path
from zoneinfo import ZoneInfo

from mesa_certa.config import get_settings
from mesa_certa.db.reset import upgrade
from mesa_certa.db.seed import is_empty, seed
from mesa_certa.db.session import create_db_engine, create_session_factory
from mesa_certa.domain.date_resolver import SystemClock
from mesa_certa.rag.embedder import Embedder
from mesa_certa.rag.ingest import ingest_directory
from mesa_certa.rag.store import ChunkStore

MIGRATIONS_PATH = Path(__file__).resolve().parent.parent / "migrations"


def main() -> None:
    settings = get_settings()

    upgrade(settings.database_url, MIGRATIONS_PATH)
    engine = create_db_engine(settings.database_url)
    try:
        with create_session_factory(engine).begin() as session:
            if is_empty(session):
                seed(session)
                print("Banco migrado e semeado.")
            else:
                print("Banco migrado; já havia dados, seed ignorado.")
    finally:
        engine.dispose()

    store = ChunkStore(settings.chroma_path, settings.chroma_collection)
    report = ingest_directory(
        settings.knowledge_path,
        Embedder(settings.embedding_model),
        store,
        SystemClock(ZoneInfo(settings.timezone)),
    )
    print(f"Índice pronto. {report.summary()}. Total no índice: {store.count()}")


if __name__ == "__main__":
    main()
