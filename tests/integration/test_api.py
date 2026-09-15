"""API HTTP com agente de modelo roteirizado: nenhuma chamada de rede."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from mesa_certa.agent.factory import AgentApp, build_app
from mesa_certa.agent.guards import SAFE_REPLY
from mesa_certa.agent.llm import ModelUnavailable
from mesa_certa.api.main import create_app
from mesa_certa.config import Settings
from mesa_certa.domain.date_resolver import FixedClock
from mesa_certa.rag.ingest import ingest_directory
from mesa_certa.rag.store import ChunkStore
from tests.fakes import HashingEmbedder, ScriptedLLM, text_response, tool_response
from tests.integration.conftest import at


def _client(
    settings: Settings, llm: ScriptedLLM, *, debug: bool = False, api_key: bool = True
) -> Iterator[tuple[TestClient, AgentApp]]:
    configured = settings.model_copy(
        update={"debug_ui": debug, "anthropic_api_key": "sk-teste" if api_key else None}
    )
    clock = FixedClock(at(2026, 9, 15, 14))
    store = ChunkStore(configured.chroma_path, "api")
    agent_app = build_app(configured, clock, llm, HashingEmbedder(), store)
    app = create_app(configured, agent_app)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, agent_app
    agent_app.close()


@pytest.fixture
def seeded(session_factory: sessionmaker[Session]) -> sessionmaker[Session]:
    return session_factory


def test_chat_cria_sessao_e_devolve_contrato(settings: Settings, seeded: object) -> None:
    llm = ScriptedLLM(
        tool_response(("consultar_disponibilidade", {"data": "2026-09-19", "num_pessoas": 2})),
        text_response("Temos mesa no sábado a partir das 18h."),
    )
    for client, _ in _client(settings, llm):
        response = client.post("/chat", json={"message": "tem mesa pra 2 no sábado?"})

        assert response.status_code == 200
        body = response.json()
        assert body["reply"] == "Temos mesa no sábado a partir das 18h."
        assert body["session_id"]
        assert len(body["trace_id"]) == 26
        assert body["tool_calls"][0]["name"] == "consultar_disponibilidade"
        assert body["tool_calls"][0]["ok"] is True
        assert body["citations"] == []
        assert body["guard_violations"] == []
        assert body["exhausted"] is False


def test_reserva_criada_volta_com_dados_do_sistema(settings: Settings, seeded: object) -> None:
    pedido = {
        "nome": "Bruna Alves",
        "telefone": "51988887777",
        "data": "2026-09-18",
        "horario": "19:00",
        "num_pessoas": 2,
    }
    llm = ScriptedLLM(
        tool_response(("criar_reserva", pedido)),
        text_response("Reserva confirmada para sexta às 19h."),
    )
    for client, _ in _client(settings, llm):
        body = client.post("/chat", json={"message": "reserva pra 2 sexta 19h"}).json()

        reserva = body["reservation"]
        assert reserva["tipo"] == "criada"
        assert len(reserva["codigo"]) == 6
        assert (reserva["data"], reserva["horario"], reserva["num_pessoas"]) == (
            "2026-09-18",
            "19:00",
            2,
        )
        assert reserva["tolerancia_minutos"] == 20
        assert "51988887777" not in str(body)
        assert "Bruna" not in str(reserva)


def test_turno_sem_reserva_devolve_null(settings: Settings, seeded: object) -> None:
    for client, _ in _client(settings, ScriptedLLM(text_response("Olá!"))):
        assert client.post("/chat", json={"message": "oi"}).json()["reservation"] is None


def test_chat_reaproveita_a_sessao(settings: Settings, seeded: object) -> None:
    llm = ScriptedLLM(text_response("Olá!"), text_response("De novo, olá!"))
    for client, _ in _client(settings, llm):
        first = client.post("/chat", json={"message": "oi"}).json()
        second = client.post(
            "/chat", json={"session_id": first["session_id"], "message": "oi de novo"}
        ).json()

        assert second["session_id"] == first["session_id"]
        assert [m["role"] for m in llm.requests[1]["messages"]] == ["user", "assistant", "user"]


def test_sessao_desconhecida_ou_expirada_responde_410(settings: Settings, seeded: object) -> None:
    for client, _ in _client(settings, ScriptedLLM()):
        response = client.post("/chat", json={"session_id": "nao-existe", "message": "oi"})

        assert response.status_code == 410
        assert response.json() == {"error": "SESSAO_EXPIRADA"}


def test_modelo_indisponivel_responde_503(settings: Settings, seeded: object) -> None:
    for client, _ in _client(settings, ScriptedLLM(ModelUnavailable("529"))):
        response = client.post("/chat", json={"message": "oi"})

        assert response.status_code == 503
        assert response.json() == {"error": "MODELO_INDISPONIVEL"}


def test_erro_inesperado_responde_500_com_trace_id(settings: Settings, seeded: object) -> None:
    for client, agent_app in _client(settings, ScriptedLLM(RuntimeError("bug"))):
        response = client.post("/chat", json={"message": "oi"})

        assert response.status_code == 500
        body = response.json()
        assert body["error"] == "ERRO_INTERNO"
        assert agent_app.tracer.get(body["trace_id"]) is not None


@pytest.mark.parametrize("payload", [{"message": ""}, {"message": "a" * 2001}, {}])
def test_payload_invalido_responde_422(
    settings: Settings, seeded: object, payload: dict[str, str]
) -> None:
    for client, _ in _client(settings, ScriptedLLM()):
        assert client.post("/chat", json=payload).status_code == 422


def test_resposta_trocada_pela_verificacao_chega_ao_cliente(
    settings: Settings, seeded: object
) -> None:
    llm = ScriptedLLM(text_response("Reserva confirmada! Código X7Y8Z9."))
    for client, _ in _client(settings, llm):
        body = client.post("/chat", json={"message": "confirma aí"}).json()

        assert body["reply"] == SAFE_REPLY
        assert "CONFIRMACAO_SEM_TOOL" in body["guard_violations"]


def test_cors_libera_a_origem_do_front(settings: Settings, seeded: object) -> None:
    for client, _ in _client(settings, ScriptedLLM()):
        response = client.options(
            "/chat",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_health_degradado_sem_indice_e_sem_chave(settings: Settings, seeded: object) -> None:
    for client, _ in _client(settings, ScriptedLLM(), api_key=False):
        response = client.get("/health")

        assert response.status_code == 503
        assert response.json() == {
            "status": "degradado",
            "checks": {"banco": True, "indice": False, "chave_api": False},
        }


def test_health_ok_com_indice_e_chave(settings: Settings, seeded: object) -> None:
    for client, agent_app in _client(settings, ScriptedLLM()):
        agent_app.store.upsert(["x#a#0"], ["texto"], [[1.0] * 384], [{"source": "x.md"}])

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/traces/01ABC"), ("post", "/admin/reindex"), ("get", "/reservations/K7M2QP")],
)
def test_rotas_de_debug_nao_existem_sem_debug_ui(
    settings: Settings, seeded: object, method: str, path: str
) -> None:
    for client, _ in _client(settings, ScriptedLLM()):
        assert getattr(client, method)(path).status_code == 404


def test_trace_do_turno_em_modo_debug(settings: Settings, seeded: object) -> None:
    llm = ScriptedLLM(text_response("Olá! Seu telefone 51988887777 ficou anotado."))
    for client, _ in _client(settings, llm, debug=True):
        trace_id = client.post("/chat", json={"message": "sou 51988887777"}).json()["trace_id"]

        response = client.get(f"/traces/{trace_id}")

        assert response.status_code == 200
        trace = response.json()
        assert trace["trace_id"] == trace_id
        assert "51988887777" not in response.text
        assert client.get("/traces/NAO-EXISTE").json() == {"error": "TRACE_NAO_ENCONTRADO"}


def test_reserva_direta_em_modo_debug(settings: Settings, seeded: object) -> None:
    for client, _ in _client(settings, ScriptedLLM(), debug=True):
        found = client.get("/reservations/k7m2qp")
        missing = client.get("/reservations/ZZZZZZ")

        assert found.status_code == 200
        assert found.json()["codigo"] == "K7M2QP"
        assert "51988887777" not in found.text
        assert missing.status_code == 404
        assert missing.json() == {"error": "RESERVA_NAO_ENCONTRADA"}


def test_reindex_em_modo_debug(settings: Settings, seeded: object, tmp_path: object) -> None:
    knowledge = settings.knowledge_path
    knowledge.mkdir(parents=True, exist_ok=True)
    (knowledge / "casa.md").write_text(
        "# Casa\n\n## Horários\n\n### Domingo\n\nAbrimos ao meio-dia e fechamos às 16h.\n",
        encoding="utf-8",
    )
    for client, agent_app in _client(settings, ScriptedLLM(), debug=True):
        first = client.post("/admin/reindex").json()
        second = client.post("/admin/reindex").json()

        assert first["criados"] == 1
        assert second == {"criados": 0, "atualizados": 0, "removidos": 0, "inalterados": 1}
        assert agent_app.store.count() == 1
        # Mesmo resultado que a ingestão por linha de comando.
        assert (
            ingest_directory(knowledge, HashingEmbedder(), agent_app.store, agent_app.clock).writes
            == 0
        )
