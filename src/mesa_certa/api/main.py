"""Aplicação FastAPI: montagem, CORS e tradução de erros para HTTP (SDD §9.3).

Erro de tool nunca chega aqui; o loop o devolve ao modelo. Chegam só falhas de sessão,
de entrada, do modelo e erros inesperados.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mesa_certa.agent.factory import AgentApp, build_app, build_clock
from mesa_certa.agent.llm import ModelUnavailable
from mesa_certa.agent.loop import TRACE_ID_ATTR
from mesa_certa.agent.session import SessionExpired
from mesa_certa.api.routes import debug_router, router
from mesa_certa.config import Settings, get_settings
from mesa_certa.observability.logging import configure_logging
from mesa_certa.sanitize import MessageTooLong

logger = structlog.get_logger(__name__)


def create_app(settings: Settings | None = None, agent_app: AgentApp | None = None) -> FastAPI:
    """Monta a aplicação. Nos testes, `agent_app` injeta um agente com modelo falso."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        owned = app.state.agent_app is None
        if owned:
            app.state.agent_app = build_app(settings, build_clock(settings))
        try:
            yield
        finally:
            if owned:
                app.state.agent_app.close()

    app = FastAPI(title="Mesa Certa", version="0.1.0", lifespan=lifespan)
    app.state.agent_app = agent_app
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)
    app.include_router(debug_router)
    _register_error_handlers(app)
    return app


def _error(status_code: int, error: str, **extra: str | None) -> JSONResponse:
    body = {"error": error, **{k: v for k, v in extra.items() if v is not None}}
    return JSONResponse(status_code=status_code, content=body)


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(SessionExpired)
    async def _session_expired(_: Request, __: SessionExpired) -> JSONResponse:
        return _error(410, "SESSAO_EXPIRADA")

    @app.exception_handler(MessageTooLong)
    async def _message_too_long(_: Request, exc: MessageTooLong) -> JSONResponse:
        return _error(422, "MENSAGEM_LONGA", detail=str(exc))

    @app.exception_handler(ModelUnavailable)
    async def _model_unavailable(_: Request, exc: ModelUnavailable) -> JSONResponse:
        logger.warning("modelo_indisponivel", erro=str(exc))
        return _error(503, "MODELO_INDISPONIVEL")

    @app.exception_handler(HTTPException)
    async def _http(_: Request, exc: HTTPException) -> JSONResponse:
        return _error(exc.status_code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        trace_id = getattr(exc, TRACE_ID_ATTR, None)
        logger.exception("erro_interno", trace_id=trace_id)
        return _error(500, "ERRO_INTERNO", trace_id=trace_id)


app = create_app()
