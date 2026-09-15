"""Montagem das dependências do agente a partir das Settings.

Usada pelo chat de terminal e pela API, para que os dois montem o sistema igual.
"""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic
from sqlalchemy import Engine

from mesa_certa.agent.llm import AnthropicLLM, LLMClient
from mesa_certa.agent.loop import AgentLoop
from mesa_certa.agent.session import SessionStore
from mesa_certa.config import Settings
from mesa_certa.db.session import create_db_engine, create_session_factory
from mesa_certa.domain.availability import AvailabilityService
from mesa_certa.domain.date_resolver import Clock, FixedClock, SystemClock
from mesa_certa.domain.menu import MenuService
from mesa_certa.domain.reservations import ReservationService
from mesa_certa.observability.tracing import Tracer
from mesa_certa.rag.embedder import Embedder, TextEmbedder
from mesa_certa.rag.retriever import Retriever
from mesa_certa.rag.store import ChunkStore
from mesa_certa.tools import ToolServices, build_registry
from mesa_certa.tools.registry import ToolRegistry


@dataclass
class AgentApp:
    settings: Settings
    clock: Clock
    engine: Engine
    registry: ToolRegistry
    sessions: SessionStore
    tracer: Tracer
    agent: AgentLoop
    embedder: TextEmbedder
    store: ChunkStore

    def close(self) -> None:
        self.engine.dispose()


def build_clock(settings: Settings, fixed_at: datetime | None = None) -> Clock:
    """Relógio fixo se pedido (argumento ou FIXED_NOW), senão o do sistema no fuso da casa."""
    fixed = fixed_at or settings.fixed_now
    return FixedClock(fixed) if fixed else SystemClock(ZoneInfo(settings.timezone))


WORKSPACE_HEADER = "anthropic-workspace-id"


def build_llm(settings: Settings) -> AnthropicLLM:
    key = settings.anthropic_api_key
    workspace = settings.anthropic_workspace_id
    headers = {WORKSPACE_HEADER: workspace} if workspace else None
    # Sem chave nas Settings, o SDK resolve credenciais do ambiente ou do perfil do `ant`.
    client = (
        anthropic.Anthropic(api_key=key.get_secret_value(), default_headers=headers)
        if key
        else anthropic.Anthropic(default_headers=headers)
    )
    return AnthropicLLM(
        client, settings.model_name, settings.model_max_tokens, settings.model_effort
    )


def build_retriever(settings: Settings, embedder: TextEmbedder, store: ChunkStore) -> Retriever:
    return Retriever(
        embedder,
        store,
        top_k=settings.rag_top_k,
        similarity_threshold=settings.rag_similarity_threshold,
        max_context_chars=settings.rag_max_context_chars,
    )


def build_app(
    settings: Settings,
    clock: Clock,
    llm: LLMClient | None = None,
    embedder: TextEmbedder | None = None,
    store: ChunkStore | None = None,
) -> AgentApp:
    embedder = embedder or Embedder(settings.embedding_model)
    store = store or ChunkStore(settings.chroma_path, settings.chroma_collection)
    engine = create_db_engine(settings.database_url)
    factory = create_session_factory(engine)
    services = ToolServices(
        availability=AvailabilityService(factory, clock),
        reservations=ReservationService(factory, clock),
        menu=MenuService(factory),
        clock=clock,
    )
    registry = build_registry(services, build_retriever(settings, embedder, store))
    tracer = Tracer(clock, settings.trace_path)
    agent = AgentLoop(
        llm or build_llm(settings),
        registry,
        clock,
        tracer,
        max_iterations=settings.agent_max_iterations,
    )
    sessions = SessionStore(clock, settings.session_ttl_minutes, settings.session_max_messages)
    return AgentApp(settings, clock, engine, registry, sessions, tracer, agent, embedder, store)
