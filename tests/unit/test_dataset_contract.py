"""Contrato entre evals/dataset.yaml e o código real (chunker, tools)."""

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from mesa_certa.rag.chunker import chunk_directory

ROOT = Path(__file__).resolve().parents[2]
TOOLS = {
    "buscar_conhecimento",
    "consultar_disponibilidade",
    "criar_reserva",
    "consultar_reserva",
    "cancelar_reserva",
    "listar_pratos_do_dia",
}
REQUIRED_FIELDS = {
    "id",
    "categoria",
    "referencias",
    "pergunta",
    "contexto_data",
    "tools_esperadas",
    "chunks_esperados",
    "deve_citar_fonte",
    "deve_recusar",
    "termos_obrigatorios",
    "termos_proibidos",
}
DISTRIBUTION = {
    "rag_cardapio": 8,
    "rag_politicas": 6,
    "disponibilidade": 5,
    "reserva": 6,
    "pratos_do_dia": 2,
    "composto": 3,
    "fora_da_base": 3,
    "adversarial": 8,
}
ID_PREFIX = {
    "rag_cardapio": "rag-",
    "rag_politicas": "rag-",
    "disponibilidade": "tool-",
    "reserva": "tool-",
    "pratos_do_dia": "tool-",
    "composto": "comp-",
    "fora_da_base": "neg-",
    "adversarial": "adv-",
}


@pytest.fixture(scope="module")
def cases() -> list[dict[str, Any]]:
    data = yaml.safe_load((ROOT / "evals" / "dataset.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


def test_todo_chunk_esperado_existe(cases: list[dict[str, Any]]) -> None:
    known = {c.chunk_id for c in chunk_directory(ROOT / "data" / "knowledge")}
    missing = {
        (case["id"], chunk_id)
        for case in cases
        for chunk_id in case["chunks_esperados"]
        if chunk_id not in known
    }
    assert missing == set()


def test_campos_obrigatorios_e_ids(cases: list[dict[str, Any]]) -> None:
    for case in cases:
        assert set(case) >= REQUIRED_FIELDS, case.get("id")
        assert set(case) <= REQUIRED_FIELDS | {"tools_alternativas"}, case["id"]
        assert case["id"].startswith(ID_PREFIX[case["categoria"]])
    assert len({c["id"] for c in cases}) == len(cases)


def test_distribuicao(cases: list[dict[str, Any]]) -> None:
    assert len(cases) == 41
    assert Counter(c["categoria"] for c in cases) == DISTRIBUTION


def test_contexto_data_com_fuso(cases: list[dict[str, Any]]) -> None:
    for case in cases:
        moment = datetime.fromisoformat(case["contexto_data"])
        assert moment.utcoffset() is not None, case["id"]


def test_tools_conhecidas(cases: list[dict[str, Any]]) -> None:
    for case in cases:
        sets = [case["tools_esperadas"], *case.get("tools_alternativas", [])]
        for tool_set in sets:
            assert set(tool_set) <= TOOLS, case["id"]


def test_termos_sao_texto_ou_lista_de_sinonimos(cases: list[dict[str, Any]]) -> None:
    for case in cases:
        for term in case["termos_obrigatorios"]:
            assert isinstance(term, str) or (
                isinstance(term, list) and term and all(isinstance(t, str) for t in term)
            ), case["id"]
        assert all(isinstance(t, str) for t in case["termos_proibidos"]), case["id"]


def test_coerencia_de_rotulos(cases: list[dict[str, Any]]) -> None:
    for case in cases:
        if case["categoria"] in {"fora_da_base", "adversarial"}:
            assert case["deve_recusar"] is True, case["id"]
            assert case["chunks_esperados"] == [], case["id"]
        if case["deve_citar_fonte"]:
            assert case["chunks_esperados"], case["id"]
