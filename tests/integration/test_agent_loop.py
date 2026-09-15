"""Loop do agente com modelo roteirizado: nenhuma chamada de rede."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from mesa_certa.agent.llm import ModelUnavailable
from mesa_certa.agent.loop import EXHAUSTED_REPLY, REFUSAL_REPLY, AgentLoop
from mesa_certa.agent.session import Session, SessionStore
from mesa_certa.config import Settings
from mesa_certa.domain.availability import AvailabilityService
from mesa_certa.domain.date_resolver import FixedClock
from mesa_certa.domain.errors import ReservationNotFound
from mesa_certa.domain.menu import MenuService
from mesa_certa.domain.reservations import ReservationService
from mesa_certa.observability.tracing import Tracer
from mesa_certa.rag.retriever import Retriever
from mesa_certa.rag.store import ChunkStore
from mesa_certa.tools import ToolServices, build_registry
from mesa_certa.tools.base import Tool
from mesa_certa.tools.registry import ToolRegistry
from tests.fakes import HashingEmbedder, ScriptedLLM, text_response, tool_response


class _EcoInput(BaseModel):
    texto: str


class _BuscaInput(BaseModel):
    pergunta: str


class _CodigoInput(BaseModel):
    codigo: str


def _busca(params: _BuscaInput) -> dict[str, Any]:
    return {
        "trechos": [
            {
                "indice": 1,
                "fonte": "cardapio.md",
                "secao": "Pratos principais › Opções sem glúten",
                "chunk_id": "cardapio.md#pratos-principais>opcoes-sem-gluten#0",
                "relevancia": 0.9,
                "conteudo": "Moqueca de banana-da-terra...",
            }
        ],
        "encontrou_informacao": True,
    }


def _consulta(params: _CodigoInput) -> dict[str, Any]:
    raise ReservationNotFound(details={"codigo": params.codigo})


@pytest.fixture
def registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(Tool("eco", "Ecoa o texto.", _EcoInput, lambda p: {"texto": p.texto}))
    registry.register(Tool("buscar_conhecimento", "Busca.", _BuscaInput, _busca))
    registry.register(Tool("consultar_reserva", "Consulta.", _CodigoInput, _consulta))
    return registry


@pytest.fixture
def tracer_path(tmp_path: Path) -> Path:
    return tmp_path / "traces"


def _agent(
    llm: ScriptedLLM,
    registry: ToolRegistry,
    clock: FixedClock,
    tracer_path: Path,
    max_iterations: int = 8,
) -> AgentLoop:
    return AgentLoop(llm, registry, clock, Tracer(clock, tracer_path), max_iterations)


def _session(clock: FixedClock) -> Session:
    return SessionStore(clock).create()


def _traces(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for f in path.glob("*.jsonl") for line in f.read_text("utf-8").splitlines()
    ]


def test_turno_sem_tool(registry: ToolRegistry, clock: FixedClock, tracer_path: Path) -> None:
    llm = ScriptedLLM(text_response("Olá! Como posso ajudar?"))
    session = _session(clock)

    result = _agent(llm, registry, clock, tracer_path).run_turn(session, "oi")

    assert result.reply == "Olá! Como posso ajudar?"
    assert result.iterations == 1
    assert result.tool_calls == []
    assert result.exhausted is False
    assert result.usage.input_tokens == 100
    assert result.usage.cache_read_input_tokens == 80
    pedido = llm.requests[0]
    assert pedido["messages"] == [{"role": "user", "content": "oi"}]
    assert "2026-09-15 14:00 (terça)" in pedido["system"][1]["text"]
    assert {t["name"] for t in pedido["tools"]} == {
        "eco",
        "buscar_conhecimento",
        "consultar_reserva",
    }
    assert [m["role"] for m in session.messages] == ["user", "assistant"]


def test_turno_com_uma_tool(registry: ToolRegistry, clock: FixedClock, tracer_path: Path) -> None:
    llm = ScriptedLLM(tool_response(("eco", {"texto": "abc"})), text_response("Ecoei abc."))
    session = _session(clock)

    result = _agent(llm, registry, clock, tracer_path).run_turn(session, "ecoa abc")

    assert result.reply == "Ecoei abc."
    assert result.iterations == 2
    assert [(c.name, c.ok) for c in result.tool_calls] == [("eco", True)]
    retorno = llm.requests[1]["messages"][-1]
    assert retorno["role"] == "user"
    assert retorno["content"] == [
        {
            "type": "tool_result",
            "tool_use_id": "toolu_1",
            "content": json.dumps({"ok": True, "data": {"texto": "abc"}}),
            "is_error": False,
        }
    ]
    assert llm.requests[1]["messages"][1]["content"][0]["type"] == "tool_use"


def test_duas_tools_na_mesma_resposta_voltam_num_unico_bloco(
    registry: ToolRegistry, clock: FixedClock, tracer_path: Path
) -> None:
    llm = ScriptedLLM(
        tool_response(
            ("eco", {"texto": "sábado"}), ("buscar_conhecimento", {"pergunta": "glúten"})
        ),
        text_response("Temos mesa e opções sem glúten.\n\nFonte: cardapio.md › Pratos principais"),
    )
    session = _session(clock)

    result = _agent(llm, registry, clock, tracer_path).run_turn(session, "mesa e sem glúten?")

    retorno = llm.requests[1]["messages"][-1]["content"]
    assert [b["tool_use_id"] for b in retorno] == ["toolu_1", "toolu_2"]
    assert [c.name for c in result.tool_calls] == ["eco", "buscar_conhecimento"]
    assert [c.chunk_id for c in result.citations] == [
        "cardapio.md#pratos-principais>opcoes-sem-gluten#0"
    ]
    assert result.citations[0].source == "cardapio.md"
    trace = _traces(tracer_path)[0]
    assert trace["retrievals"][0]["chunk_ids"] == [
        "cardapio.md#pratos-principais>opcoes-sem-gluten#0"
    ]


def test_erro_de_tool_volta_ao_modelo_como_is_error(
    registry: ToolRegistry, clock: FixedClock, tracer_path: Path
) -> None:
    llm = ScriptedLLM(
        tool_response(("consultar_reserva", {"codigo": "ZZZZZZ"})),
        text_response("Não encontrei a reserva ZZZZZZ. Confira o código."),
    )
    session = _session(clock)

    result = _agent(llm, registry, clock, tracer_path).run_turn(session, "reserva ZZZZZZ")

    bloco = llm.requests[1]["messages"][-1]["content"][0]
    assert bloco["is_error"] is True
    assert json.loads(bloco["content"])["error"]["code"] == "RESERVA_NAO_ENCONTRADA"
    assert result.tool_calls[0].ok is False
    assert result.tool_calls[0].error_code == "RESERVA_NAO_ENCONTRADA"
    assert "Não encontrei" in result.reply


def test_argumento_invalido_e_tool_desconhecida_nao_estouram(
    registry: ToolRegistry, clock: FixedClock, tracer_path: Path
) -> None:
    llm = ScriptedLLM(
        tool_response(("eco", {"errado": 1}), ("nao_existe", {})),
        text_response("Tive um problema técnico."),
    )

    result = _agent(llm, registry, clock, tracer_path).run_turn(_session(clock), "?")

    assert [c.error_code for c in result.tool_calls] == [
        "ARGUMENTOS_INVALIDOS",
        "TOOL_DESCONHECIDA",
    ]
    assert result.reply == "Tive um problema técnico."


def test_estouro_de_iteracoes(registry: ToolRegistry, clock: FixedClock, tracer_path: Path) -> None:
    llm = ScriptedLLM(tool_response(("eco", {"texto": "de novo"})), repeat_last=True)
    session = _session(clock)

    result = _agent(llm, registry, clock, tracer_path, max_iterations=3).run_turn(session, "loop")

    assert result.exhausted is True
    assert result.reply == EXHAUSTED_REPLY
    assert "(51) 3030-4050" in result.reply
    assert result.iterations == 3
    assert len(llm.requests) == 3
    assert len(result.tool_calls) == 3
    assert session.messages[-1] == {
        "role": "assistant",
        "content": [{"type": "text", "text": EXHAUSTED_REPLY}],
    }
    assert _traces(tracer_path)[0]["exhausted"] is True


def test_proximo_turno_leva_historico_completo(
    registry: ToolRegistry, clock: FixedClock, tracer_path: Path
) -> None:
    llm = ScriptedLLM(
        tool_response(("eco", {"texto": "1"})),
        text_response("primeira"),
        text_response("segunda"),
    )
    agent = _agent(llm, registry, clock, tracer_path)
    session = _session(clock)

    agent.run_turn(session, "turno 1")
    agent.run_turn(session, "turno 2")

    roles = [m["role"] for m in llm.requests[2]["messages"]]
    assert roles == ["user", "assistant", "user", "assistant", "user"]
    assert llm.requests[2]["messages"][-1]["content"] == "turno 2"


def test_resposta_truncada_descarta_tool_use_sem_resultado(
    registry: ToolRegistry, clock: FixedClock, tracer_path: Path
) -> None:
    truncada = tool_response(("eco", {"texto": "x"}), text="Vou verificar")
    truncada.stop_reason = "max_tokens"
    llm = ScriptedLLM(truncada)
    session = _session(clock)

    result = _agent(llm, registry, clock, tracer_path).run_turn(session, "oi")

    assert result.reply == "Vou verificar"
    assert result.tool_calls == []
    assert session.messages[-1]["content"] == [{"type": "text", "text": "Vou verificar"}]


def test_recusa_do_modelo_vira_resposta_padrao(
    registry: ToolRegistry, clock: FixedClock, tracer_path: Path
) -> None:
    llm = ScriptedLLM(text_response("", stop_reason="refusal"))

    result = _agent(llm, registry, clock, tracer_path).run_turn(_session(clock), "algo")

    assert result.reply == REFUSAL_REPLY


def test_modelo_indisponivel_propaga_e_fecha_trace(
    registry: ToolRegistry, clock: FixedClock, tracer_path: Path
) -> None:
    llm = ScriptedLLM(ModelUnavailable("529"))

    with pytest.raises(ModelUnavailable):
        _agent(llm, registry, clock, tracer_path).run_turn(_session(clock), "oi")

    trace = _traces(tracer_path)[0]
    assert trace["error"] == "ModelUnavailable"
    assert trace["final_reply"] == ""


def test_reserva_ponta_a_ponta_sobre_banco_semeado_com_trace_mascarado(
    settings: Settings, session_factory: sessionmaker[DbSession], clock: FixedClock
) -> None:
    services = ToolServices(
        availability=AvailabilityService(session_factory, clock),
        reservations=ReservationService(session_factory, clock),
        menu=MenuService(session_factory),
        clock=clock,
    )
    retriever = Retriever(HashingEmbedder(), ChunkStore(settings.chroma_path, "vazia"))
    registry = build_registry(services, retriever)
    pedido = {
        "nome": "Bruna Alves",
        "telefone": "51988887777",
        "data": "2026-09-19",
        "horario": "20:00",
        "num_pessoas": 2,
    }
    llm = ScriptedLLM(
        tool_response(
            (
                "consultar_disponibilidade",
                {"data": "2026-09-19", "num_pessoas": 2, "horario": "20:00"},
            )
        ),
        tool_response(("criar_reserva", pedido)),
        text_response("Reserva confirmada."),
    )
    mensagem = "Reserva pra 2 no sábado 20h, Bruna Alves, 51988887777. Pode confirmar."

    result = _agent(llm, registry, clock, settings.trace_path).run_turn(_session(clock), mensagem)

    assert [(c.name, c.ok) for c in result.tool_calls] == [
        ("consultar_disponibilidade", True),
        ("criar_reserva", True),
    ]
    criada = json.loads(llm.requests[2]["messages"][-1]["content"][0]["content"])
    assert len(criada["data"]["codigo"]) == 6
    conteudo = (settings.trace_path / "2026-09-15.jsonl").read_text(encoding="utf-8")
    assert "51988887777" not in conteudo
    assert "51*******77" in conteudo
    # Nome em texto livre não é detectável por regex (SDD §10.2); nos argumentos, é mascarado.
    args_criacao = json.loads(conteudo)["tool_calls"][1]["args"]
    assert args_criacao["nome"] == "Bruna A."
    assert args_criacao["telefone"] == "51*******77"
