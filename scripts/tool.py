"""Chama uma tool pelo registry, como o agente faria, e imprime o envelope JSON.

Uso:
  python scripts/tool.py --listar
  python scripts/tool.py consultar_disponibilidade \
      '{"data": "2026-09-19", "num_pessoas": 6, "horario": "20:00"}'
  python scripts/tool.py cancelar_reserva '{"codigo": "K7M2QP"}' --agora 2026-09-26T17:00:00-03:00

Cancelamento e criação alteram o banco. `make seed` restaura o estado inicial.
"""

import argparse
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from mesa_certa.config import get_settings
from mesa_certa.db.session import create_db_engine, create_session_factory
from mesa_certa.domain.availability import AvailabilityService
from mesa_certa.domain.date_resolver import Clock, FixedClock, SystemClock
from mesa_certa.domain.menu import MenuService
from mesa_certa.domain.reservations import ReservationService
from mesa_certa.rag.embedder import Embedder
from mesa_certa.rag.retriever import Retriever
from mesa_certa.rag.store import ChunkStore
from mesa_certa.tools import ToolServices, build_registry


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("nome", nargs="?", help="nome da tool")
    parser.add_argument("argumentos", nargs="?", default="{}", help="argumentos em JSON")
    parser.add_argument("--agora", help="fixa o relógio, em ISO 8601 com fuso")
    parser.add_argument("--listar", action="store_true", help="lista os schemas das tools")
    args = parser.parse_args()

    settings = get_settings()
    clock: Clock = (
        FixedClock(datetime.fromisoformat(args.agora))
        if args.agora
        else SystemClock(ZoneInfo(settings.timezone))
    )
    engine = create_db_engine(settings.database_url)
    factory = create_session_factory(engine)
    services = ToolServices(
        availability=AvailabilityService(factory, clock),
        reservations=ReservationService(factory, clock),
        menu=MenuService(factory),
        clock=clock,
    )
    retriever = Retriever(
        Embedder(settings.embedding_model),
        ChunkStore(settings.chroma_path, settings.chroma_collection),
        top_k=settings.rag_top_k,
        similarity_threshold=settings.rag_similarity_threshold,
        max_context_chars=settings.rag_max_context_chars,
    )
    registry = build_registry(services, retriever)

    try:
        if args.listar or not args.nome:
            print(json.dumps(registry.schemas(), ensure_ascii=False, indent=2))
            return
        result = registry.dispatch(args.nome, json.loads(args.argumentos))
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
