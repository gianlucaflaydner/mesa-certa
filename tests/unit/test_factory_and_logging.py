from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import SecretStr

from mesa_certa.agent.factory import WORKSPACE_HEADER, build_app, build_clock, build_llm
from mesa_certa.config import Settings
from mesa_certa.domain.date_resolver import FixedClock, SystemClock
from mesa_certa.observability.logging import configure_logging, mask_event
from mesa_certa.rag.retriever import Retriever
from mesa_certa.rag.store import ChunkStore
from tests.fakes import HashingEmbedder, ScriptedLLM, text_response

AGORA = datetime(2026, 9, 15, 14, tzinfo=ZoneInfo("America/Sao_Paulo"))


def test_build_clock_fixo_ou_do_sistema(settings: Settings) -> None:
    assert isinstance(build_clock(settings, AGORA), FixedClock)
    assert isinstance(build_clock(settings), SystemClock)


def test_build_llm_usa_modelo_effort_e_limite_das_settings(settings: Settings) -> None:
    configurado = settings.model_copy(
        update={"anthropic_api_key": SecretStr("sk-teste"), "model_effort": "low"}
    )

    llm = build_llm(configurado)

    assert llm.model == "claude-sonnet-5"
    assert llm.effort == "low"
    assert llm.max_tokens == 16000
    assert WORKSPACE_HEADER not in llm._client.default_headers


def test_build_llm_envia_workspace_quando_configurado(settings: Settings) -> None:
    configurado = settings.model_copy(
        update={"anthropic_api_key": SecretStr("sk-teste"), "anthropic_workspace_id": "wrkspc_123"}
    )

    llm = build_llm(configurado)

    assert llm._client.default_headers[WORKSPACE_HEADER] == "wrkspc_123"


def test_build_app_monta_agente_que_conclui_turno(settings: Settings) -> None:
    clock = FixedClock(AGORA)
    retriever = Retriever(HashingEmbedder(), ChunkStore(settings.chroma_path, "vazia"))
    app = build_app(settings, clock, ScriptedLLM(text_response("Olá!")), retriever)
    try:
        session = app.sessions.create()
        result = app.agent.run_turn(session, "oi")

        assert result.reply == "Olá!"
        assert len(app.registry.names) == 6
        assert app.tracer.get(result.trace_id) is not None
        assert (settings.trace_path / "2026-09-15.jsonl").exists()
    finally:
        app.close()


def test_mask_event_mascara_campos_e_texto() -> None:
    evento = {"event": "contato 51988887777", "telefone": "51988887777", "nome": "Bruna Alves"}

    assert mask_event(None, "info", evento) == {
        "event": "contato 51*******77",
        "telefone": "51*******77",
        "nome": "Bruna A.",
    }


def test_configure_logging_nao_falha() -> None:
    configure_logging("DEBUG")
