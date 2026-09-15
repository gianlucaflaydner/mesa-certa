import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from mesa_certa.domain.date_resolver import FixedClock
from mesa_certa.observability.tracing import Tracer, new_ulid
from mesa_certa.tools.base import ToolResult

AGORA = datetime(2026, 9, 15, 14, tzinfo=ZoneInfo("America/Sao_Paulo"))


def test_ulid_tem_26_caracteres_crockford_e_ordena_por_tempo() -> None:
    a = new_ulid(1_000)
    b = new_ulid(2_000)

    assert re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", a)
    assert a < b
    assert new_ulid() != new_ulid()


def test_trace_mascara_mensagem_argumentos_e_resposta(tmp_path: Path) -> None:
    tracer = Tracer(FixedClock(AGORA), tmp_path)
    trace = tracer.start_turn("sessao", "Sou a Bruna, fone 51988887777")
    trace.record_tool_call(
        "criar_reserva",
        {"nome": "Bruna Alves", "telefone": "51988887777", "email": "bruna@gmail.com"},
        ToolResult.success({"codigo": "K7M2QP", "nome": "Bruna Alves"}),
        12,
    )

    tracer.finish(trace, "Reserva feita para 51988887777.")

    linha = (tmp_path / "2026-09-15.jsonl").read_text(encoding="utf-8")
    assert "51988887777" not in linha
    assert "bruna@gmail.com" not in linha
    assert "Bruna Alves" not in linha
    gravado = json.loads(linha)
    assert gravado["tool_calls"][0]["args"]["telefone"] == "51*******77"
    assert gravado["tool_calls"][0]["args"]["nome"] == "Bruna A."
    assert gravado["final_reply"] == "Reserva feita para 51*******77."
    assert tracer.get(trace.trace_id) is trace


def test_busca_registra_retrieval_com_chunks_e_scores(tmp_path: Path) -> None:
    tracer = Tracer(FixedClock(AGORA), None)
    trace = tracer.start_turn("sessao", "tem opção sem glúten?")
    dados = {
        "trechos": [
            {"chunk_id": "cardapio.md#a#0", "relevancia": 0.91},
            {"chunk_id": "faq.md#b#0", "relevancia": 0.84},
        ],
        "encontrou_informacao": True,
    }

    trace.record_tool_call(
        "buscar_conhecimento", {"pergunta": "opções sem glúten"}, ToolResult.success(dados), 30
    )
    trace.record_tool_call(
        "buscar_conhecimento",
        {"pergunta": "sulfito"},
        ToolResult.success({"trechos": [], "encontrou_informacao": False}),
        25,
    )

    primeira, segunda = trace.retrievals
    assert primeira.chunk_ids == ["cardapio.md#a#0", "faq.md#b#0"]
    assert primeira.scores == [0.91, 0.84]
    assert primeira.below_threshold is False
    assert segunda.below_threshold is True


def test_erro_de_tool_registra_codigo() -> None:
    tracer = Tracer(FixedClock(AGORA), None)
    trace = tracer.start_turn("sessao", "cancela X")

    trace.record_tool_call(
        "cancelar_reserva", {"codigo": "X"}, ToolResult.failure("JA_CANCELADA", "Já cancelada."), 5
    )

    assert trace.tool_calls[0].ok is False
    assert trace.tool_calls[0].error_code == "JA_CANCELADA"
    assert trace.retrievals == []


def test_falha_de_escrita_nao_derruba_o_turno(tmp_path: Path) -> None:
    arquivo = tmp_path / "ocupado"
    arquivo.write_text("não é diretório", encoding="utf-8")
    tracer = Tracer(FixedClock(AGORA), arquivo)
    trace = tracer.start_turn("sessao", "oi")

    tracer.finish(trace, "olá")

    assert tracer.get(trace.trace_id) is trace
