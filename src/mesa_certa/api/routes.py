"""Rotas da API (SDD §9.1).

`/chat` e `/health` são públicas. As rotas de depuração só existem com `DEBUG_UI=true`;
fora disso respondem 404, como se não existissem.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import text

from mesa_certa.agent.factory import AgentApp
from mesa_certa.api.dto import ChatRequest, ChatResponse, ErrorOut, HealthOut, ReindexOut
from mesa_certa.rag.ingest import ingest_directory
from mesa_certa.tools.documents import MENU_PDF_DOWNLOAD_NAME

router = APIRouter()
debug_router = APIRouter()


def get_agent_app(request: Request) -> AgentApp:
    agent_app: AgentApp = request.app.state.agent_app
    return agent_app


App = Annotated[AgentApp, Depends(get_agent_app)]


def require_debug(agent_app: App) -> None:
    if not agent_app.settings.debug_ui:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={410: {"model": ErrorOut}, 422: {"model": ErrorOut}, 503: {"model": ErrorOut}},
)
def chat(body: ChatRequest, agent_app: App) -> ChatResponse:
    # Rota síncrona de propósito: o FastAPI a executa numa thread, e a chamada ao modelo
    # bloqueia por alguns segundos.
    session = agent_app.sessions.get_or_create(body.session_id)
    with session.lock:
        turn = agent_app.agent.run_turn(session, body.message)
    return ChatResponse.from_turn(turn)


@router.get("/health", response_model=HealthOut, responses={503: {"model": HealthOut}})
def health(agent_app: App, response: Response) -> HealthOut:
    checks = {
        "banco": _database_ok(agent_app),
        "indice": _index_ok(agent_app),
        "chave_api": agent_app.settings.anthropic_api_key is not None,
    }
    healthy = all(checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthOut(status="ok" if healthy else "degradado", checks=checks)


@router.get("/arquivos/cardapio.pdf", response_class=FileResponse)
def menu_pdf(agent_app: App, download: bool = False) -> FileResponse:
    """Cardápio completo. `?download=1` pede ao navegador para salvar em vez de abrir."""
    path = agent_app.settings.menu_pdf_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="CARDAPIO_INDISPONIVEL")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=MENU_PDF_DOWNLOAD_NAME,
        content_disposition_type="attachment" if download else "inline",
    )


@debug_router.get("/traces/{trace_id}", dependencies=[Depends(require_debug)])
def get_trace(trace_id: str, agent_app: App) -> dict[str, Any]:
    trace = agent_app.tracer.get(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="TRACE_NAO_ENCONTRADO")
    return trace.to_dict()


@debug_router.post(
    "/admin/reindex", response_model=ReindexOut, dependencies=[Depends(require_debug)]
)
def reindex(agent_app: App) -> ReindexOut:
    report = ingest_directory(
        agent_app.settings.knowledge_path, agent_app.embedder, agent_app.store, agent_app.clock
    )
    return ReindexOut(
        criados=len(report.created),
        atualizados=len(report.updated),
        removidos=len(report.removed),
        inalterados=len(report.unchanged),
    )


@debug_router.get("/reservations/{code}", dependencies=[Depends(require_debug)])
def get_reservation(code: str, agent_app: App) -> dict[str, Any]:
    # Pelo registry, para devolver exatamente o que o agente vê, sem telefone nem e-mail.
    result = agent_app.registry.dispatch("consultar_reserva", {"codigo": code})
    if not result.ok:
        assert result.error is not None
        raise HTTPException(status_code=404, detail=result.error.code)
    assert result.data is not None
    return result.data


def _database_ok(agent_app: AgentApp) -> bool:
    try:
        with agent_app.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _index_ok(agent_app: AgentApp) -> bool:
    try:
        return agent_app.store.count() > 0
    except Exception:
        return False
