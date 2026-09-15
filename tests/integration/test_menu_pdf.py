"""Cardápio em PDF: tool enviar_cardapio, rota /arquivos/cardapio.pdf e anexo no /chat."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from mesa_certa.agent.factory import build_app
from mesa_certa.api.main import create_app
from mesa_certa.config import Settings
from mesa_certa.domain.date_resolver import FixedClock
from mesa_certa.rag.store import ChunkStore
from mesa_certa.tools.documents import MENU_PDF_URL, enviar_cardapio_tool
from mesa_certa.tools.registry import ToolRegistry
from tests.fakes import HashingEmbedder, ScriptedLLM, text_response, tool_response
from tests.integration.conftest import at

PDF_BYTES = b"%PDF-1.4\n% cardapio de teste\n%%EOF\n"


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    path = tmp_path / "Cardápio Mesa Certa.pdf"
    path.write_bytes(PDF_BYTES * 200)
    return path


def _registry(pdf_path: Path) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(enviar_cardapio_tool(pdf_path))
    return registry


def test_tool_entrega_o_cardapio(pdf: Path) -> None:
    result = _registry(pdf).dispatch("enviar_cardapio", {})

    assert result.ok
    assert result.data is not None
    assert result.data["url"] == MENU_PDF_URL
    assert result.data["arquivo"] == "cardapio-mesa-certa.pdf"
    assert result.data["tamanho_kb"] == round(pdf.stat().st_size / 1024)


def test_tool_sem_arquivo_devolve_erro_estruturado(tmp_path: Path) -> None:
    result = _registry(tmp_path / "nao-existe.pdf").dispatch("enviar_cardapio", None)

    assert not result.ok
    assert result.error is not None
    assert result.error.code == "CARDAPIO_INDISPONIVEL"


def test_cardapio_do_repositorio_existe() -> None:
    assert Settings(_env_file=None).menu_pdf_path.is_file()


def _client(settings: Settings, pdf_path: Path, llm: ScriptedLLM) -> Iterator[TestClient]:
    configured = settings.model_copy(update={"menu_pdf_path": pdf_path})
    clock = FixedClock(at(2026, 9, 15, 14))
    agent_app = build_app(
        configured, clock, llm, HashingEmbedder(), ChunkStore(configured.chroma_path, "pdf")
    )
    with TestClient(create_app(configured, agent_app)) as client:
        yield client
    agent_app.close()


@pytest.fixture
def seeded(session_factory: sessionmaker[Session]) -> sessionmaker[Session]:
    return session_factory


def test_chat_devolve_o_anexo_quando_o_modelo_envia(
    settings: Settings, seeded: object, pdf: Path
) -> None:
    llm = ScriptedLLM(
        tool_response(("enviar_cardapio", {})),
        text_response("Aqui está o cardápio completo, é só abrir ou baixar logo abaixo."),
    )
    for client in _client(settings, pdf, llm):
        body = client.post("/chat", json={"message": "me manda o cardápio?"}).json()

        assert body["attachments"] == [
            {
                "tipo": "cardapio_pdf",
                "titulo": "Cardápio Mesa Certa",
                "arquivo": "cardapio-mesa-certa.pdf",
                "url": "/arquivos/cardapio.pdf",
                "tamanho_kb": round(pdf.stat().st_size / 1024),
            }
        ]
        retorno = json.loads(llm.requests[1]["messages"][-1]["content"][0]["content"])
        assert retorno["ok"] is True


def test_turno_sem_envio_nao_tem_anexo(settings: Settings, seeded: object, pdf: Path) -> None:
    for client in _client(settings, pdf, ScriptedLLM(text_response("Olá!"))):
        assert client.post("/chat", json={"message": "oi"}).json()["attachments"] == []


def test_rota_abre_o_pdf_no_navegador(settings: Settings, seeded: object, pdf: Path) -> None:
    for client in _client(settings, pdf, ScriptedLLM()):
        response = client.get("/arquivos/cardapio.pdf")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["content-disposition"].startswith("inline")
        assert "cardapio-mesa-certa.pdf" in response.headers["content-disposition"]
        assert response.content == pdf.read_bytes()


def test_rota_com_download_pede_para_salvar(settings: Settings, seeded: object, pdf: Path) -> None:
    for client in _client(settings, pdf, ScriptedLLM()):
        response = client.get("/arquivos/cardapio.pdf?download=1")

        assert response.headers["content-disposition"].startswith("attachment")


def test_rota_sem_arquivo_responde_404(settings: Settings, seeded: object, tmp_path: Path) -> None:
    for client in _client(settings, tmp_path / "sumiu.pdf", ScriptedLLM()):
        response = client.get("/arquivos/cardapio.pdf")

        assert response.status_code == 404
        assert response.json() == {"error": "CARDAPIO_INDISPONIVEL"}
