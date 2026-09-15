"""Montagem das dependências do agente a partir das Settings.

Usada pelo chat de terminal agora e pela API na F5, para que os dois montem o sistema igual.
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
from mesa_certa.rag.embedder import Embedder
from mesa_certa.rag.retriever import Retriever
from mesa_certa.rag.store import ChunkStore
from mesa_certa.tools import ToolServices, build_registry
from mesa_certa.tools.registry import ToolRegistry


@dataclass
class AgentApp:
    engine: Engine
    registry: ToolRegistry
    sessions: SessionStore
    tracer: Tracer
    agent: AgentLoop

    def close(self) -> None:
        self.engine.dispose()


def build_clock(settings: Settings, fixed_at: datetime | None = None) -> Clock:
    return FixedClock(fixed_at) if fixed_at else SystemClock(ZoneInfo(settings.timezone))


def build_llm(settings: Settings) -> AnthropicLLM:
    key = settings.anthropic_api_key
    # Sem chave nas Settings, o SDK resolve credenciais do ambiente ou do perfil do `ant`.
    client = anthropic.Anthropic(api_key=key.get_secret_value()) if key else anthropic.Anthropic()
    return AnthropicLLM(
        client, settings.model_name, settings.model_max_tokens, settings.model_effort
    )


def build_retriever(settings: Settings) -> Retriever:
    return Retriever(
        Embedder(settings.embedding_model),
        ChunkStore(settings.chroma_path, settings.chroma_collection),
        top_k=settings.rag_top_k,
        similarity_threshold=settings.rag_similarity_threshold,
        max_context_chars=settings.rag_max_context_chars,
    )


def build_app(
    settings: Settings,
    clock: Clock,
    llm: LLMClient | None = None,
    retriever: Retriever | None = None,
) -> AgentApp:
    engine = create_db_engine(settings.database_url)
    factory = create_session_factory(engine)
    services = ToolServices(
        availability=AvailabilityService(factory, clock),
        reservations=ReservationService(factory, clock),
        menu=MenuService(factory),
        clock=clock,
    )
    registry = build_registry(services, retriever or build_retriever(settings))
    tracer = Tracer(clock, settings.trace_path)
    agent = AgentLoop(
        llm or build_llm(settings),
        registry,
        clock,
        tracer,
        max_iterations=settings.agent_max_iterations,
    )
    sessions = SessionStore(clock, settings.session_ttl_minutes, settings.session_max_messages)
    return AgentApp(engine, registry, sessions, tracer, agent)
