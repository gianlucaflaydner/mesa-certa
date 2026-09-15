"""Tools via `dispatch`, sobre banco semeado e retriever de fixture."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from mesa_certa.domain.availability import AvailabilityService
from mesa_certa.domain.date_resolver import FixedClock
from mesa_certa.domain.errors import DomainError
from mesa_certa.domain.menu import MenuService
from mesa_certa.domain.reservations import ReservationService
from mesa_certa.rag.ingest import ingest_directory
from mesa_certa.rag.retriever import Retriever
from mesa_certa.rag.store import ChunkStore
from mesa_certa.tools import ToolServices, build_registry
from mesa_certa.tools.base import Tool, ToolResult
from mesa_certa.tools.menu import format_brl
from mesa_certa.tools.registry import ToolRegistry
from mesa_certa.tools.reservations import LATE_CANCELLATION_NOTICE
from tests.fakes import HashingEmbedder
from tests.integration.conftest import at

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "knowledge"


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object, ToolResult, float]] = []

    def on_tool_call(self, name: str, args: object, result: ToolResult, duration_ms: float) -> None:
        self.calls.append((name, args, result, duration_ms))


@pytest.fixture(scope="module")
def retriever(tmp_path_factory: pytest.TempPathFactory) -> Retriever:
    embedder = HashingEmbedder()
    store = ChunkStore(tmp_path_factory.mktemp("chroma"), "tools")
    ingest_directory(FIXTURES, embedder, store, FixedClock(at(2026, 9, 15, 10)))
    return Retriever(embedder, store, similarity_threshold=0.3)


@pytest.fixture
def registry(
    session_factory: sessionmaker[Session], clock: FixedClock, retriever: Retriever
) -> ToolRegistry:
    services = ToolServices(
        availability=AvailabilityService(session_factory, clock),
        reservations=ReservationService(session_factory, clock),
        menu=MenuService(session_factory),
        clock=clock,
    )
    return build_registry(services, retriever, observer=Recorder())


def ok(result: ToolResult) -> dict[str, Any]:
    assert result.ok, result.to_json()
    assert result.data is not None
    return result.data


def error_code(result: ToolResult) -> str:
    assert not result.ok, result.to_json()
    assert result.error is not None
    return result.error.code


# buscar_conhecimento


def test_busca_com_resultado(registry: ToolRegistry) -> None:
    data = ok(registry.dispatch("buscar_conhecimento", {"pergunta": "gatos na varanda"}))

    assert data["encontrou_informacao"] is True
    first = data["trechos"][0]
    assert first["indice"] == 1
    assert first["chunk_id"] == "casa.md#animais>gatos#0"
    assert first["fonte"] == "casa.md"
    assert first["secao"] == "Animais › Gatos"
    assert first["citacao"] == "casa.md › Animais › Gatos"
    assert 0 <= first["relevancia"] <= 1
    assert "mensagem" not in data


def test_busca_sem_resultado_orienta_recusa(registry: ToolRegistry) -> None:
    data = ok(registry.dispatch("buscar_conhecimento", {"pergunta": "feijoada quinta-feira"}))

    assert data["encontrou_informacao"] is False
    assert data["trechos"] == []
    assert "(51) 3030-4050" in data["mensagem"]


@pytest.mark.parametrize(
    "args", [{}, {"pergunta": "   "}, {"pergunta": "vinho", "top_k": 50}, {"pergunta": 3}]
)
def test_busca_argumentos_invalidos(registry: ToolRegistry, args: dict[str, Any]) -> None:
    assert error_code(registry.dispatch("buscar_conhecimento", args)) == "ARGUMENTOS_INVALIDOS"


# consultar_disponibilidade


def test_disponivel_tool_001(registry: ToolRegistry) -> None:
    data = ok(
        registry.dispatch(
            "consultar_disponibilidade",
            {"data": "2026-09-19", "num_pessoas": 2, "horario": "20:00"},
        )
    )

    assert data["disponivel"] is True
    assert data["zona"] == "varanda"
    assert data["dia_semana"] == "sábado"
    assert data["motivo"] is None


def test_indisponivel_com_alternativas_tool_004(registry: ToolRegistry) -> None:
    data = ok(
        registry.dispatch(
            "consultar_disponibilidade",
            {"data": "2026-09-19", "num_pessoas": 6, "horario": "20:00"},
        )
    )

    assert data["disponivel"] is False
    assert data["motivo"] == "SEM_DISPONIBILIDADE"
    assert data["alternativas"] == [
        {"horario": "21:30", "zona": "mezanino"},
        {"horario": "22:00", "zona": "mezanino"},
        {"horario": "22:30", "zona": "mezanino"},
    ]


def test_sem_horario_lista_livres_tool_002(registry: ToolRegistry) -> None:
    data = ok(
        registry.dispatch("consultar_disponibilidade", {"data": "2026-09-16", "num_pessoas": 3})
    )

    assert data["horario_solicitado"] is None
    assert data["disponivel"] is True
    assert data["alternativas"][0] == {"horario": "18:00", "zona": "salao"}


def test_dia_fechado_com_proxima_data(registry: ToolRegistry) -> None:
    result = registry.dispatch(
        "consultar_disponibilidade", {"data": "2026-09-21", "num_pessoas": 4, "horario": "20:00"}
    )

    assert error_code(result) == "DIA_FECHADO"
    assert result.error is not None
    assert result.error.details == {
        "data": "2026-09-21",
        "dia_semana": "segunda",
        "motivo": "Fechado às segundas-feiras",
        "proxima_data_aberta": "2026-09-22",
    }


def test_grupo_de_18_informa_contato(registry: ToolRegistry) -> None:
    result = registry.dispatch(
        "consultar_disponibilidade", {"data": "2026-09-19", "num_pessoas": 18}
    )

    assert error_code(result) == "GRUPO_ACIMA_DO_LIMITE"
    assert result.error is not None
    assert result.error.details["contato_eventos"] == "(51) 3030-4050"


# criar_reserva

RESERVA = {
    "nome": "Bruna Alves",
    "telefone": "(51) 98888-7777",
    "data": "2026-09-18",
    "horario": "19:00",
    "num_pessoas": 2,
}


def test_cria_reserva(registry: ToolRegistry) -> None:
    result = registry.dispatch("criar_reserva", RESERVA | {"observacoes": " aniversário "})
    data = ok(result)

    assert len(data["codigo"]) == 6
    assert data["nome"] == "Bruna Alves"
    assert (data["data"], data["horario"], data["num_pessoas"]) == ("2026-09-18", "19:00", 2)
    assert data["zona"] == "varanda"
    assert data["tolerancia_minutos"] == 20
    assert data["cancelamento_sem_onus_ate"] == "2026-09-18T15:00:00-03:00"
    assert "98888" not in result.to_json()

    found = ok(registry.dispatch("consultar_reserva", {"codigo": data["codigo"]}))
    assert found["observacoes"] == "aniversário"


@pytest.mark.parametrize(
    "changes",
    [
        {"telefone": "abc"},
        {"telefone": "1234"},
        {"nome": ""},
        {"email": "sem-arroba"},
        {"num_pessoas": "duas"},
        {"horario": None},
    ],
)
def test_criar_argumentos_invalidos(registry: ToolRegistry, changes: dict[str, Any]) -> None:
    assert error_code(registry.dispatch("criar_reserva", RESERVA | changes)) == (
        "ARGUMENTOS_INVALIDOS"
    )


def test_criar_sem_campo_obrigatorio(registry: ToolRegistry) -> None:
    args = {k: v for k, v in RESERVA.items() if k != "telefone"}
    result = registry.dispatch("criar_reserva", args)

    assert error_code(result) == "ARGUMENTOS_INVALIDOS"
    assert result.error is not None
    assert result.error.details["erros"][0]["campo"] == "telefone"


# consultar_reserva


def test_consulta_reserva_sem_expor_contato(registry: ToolRegistry) -> None:
    result = registry.dispatch("consultar_reserva", {"codigo": "k7m2qp"})
    data = ok(result)

    assert data["codigo"] == "K7M2QP"
    assert data["situacao"] == "CONFIRMADA"
    assert (data["data"], data["horario"], data["num_pessoas"]) == ("2026-09-26", "20:00", 2)
    assert data["cancelada_em"] is None
    assert "51988887777" not in result.to_json()


# cancelar_reserva


def test_cancela_dentro_da_janela_tool_010(registry: ToolRegistry) -> None:
    data = ok(registry.dispatch("cancelar_reserva", {"codigo": "K7M2QP", "motivo": "  "}))

    assert data == {
        "codigo": "K7M2QP",
        "situacao": "CANCELADA",
        "dentro_da_janela_gratuita": True,
        "aviso": None,
    }


def test_cancela_fora_da_janela_com_aviso(registry: ToolRegistry, clock: FixedClock) -> None:
    clock.instant = at(2026, 9, 26, 17)

    data = ok(registry.dispatch("cancelar_reserva", {"codigo": "K7M2QP"}))

    assert data["dentro_da_janela_gratuita"] is False
    assert data["aviso"] == LATE_CANCELLATION_NOTICE


# listar_pratos_do_dia


def test_pratos_de_hoje_pelo_relogio(registry: ToolRegistry) -> None:
    data = ok(registry.dispatch("listar_pratos_do_dia", {}))

    assert data["data"] == "2026-09-15"
    assert data["encontrou_pratos"] is True
    assert len(data["pratos"]) == 2
    assert all(p["preco_formatado"].startswith("R$ ") for p in data["pratos"])


def test_sem_pratos_na_data(registry: ToolRegistry) -> None:
    data = ok(registry.dispatch("listar_pratos_do_dia", {"data": "2026-11-10"}))

    assert data["encontrou_pratos"] is False
    assert data["pratos"] == []


def test_formato_de_preco() -> None:
    assert format_brl(89.0) == "R$ 89,00"
    assert format_brl(1234.5) == "R$ 1.234,50"


# Todo código de erro do SDD §5.8 sai de algum dispatch

ERROR_SCENARIOS: list[tuple[str, dict[str, Any], str]] = [
    (
        "consultar_disponibilidade",
        {"data": "2026-09-19", "num_pessoas": 13},
        "GRUPO_ACIMA_DO_LIMITE",
    ),
    ("consultar_disponibilidade", {"data": "2026-09-19", "num_pessoas": 0}, "GRUPO_INVALIDO"),
    ("consultar_disponibilidade", {"data": "2026-09-12", "num_pessoas": 2}, "FORA_DA_JANELA"),
    # Fechamento dentro da janela de 60 dias; 25/12 cairia antes em FORA_DA_JANELA.
    ("consultar_disponibilidade", {"data": "2026-10-14", "num_pessoas": 2}, "DIA_FECHADO"),
    (
        "consultar_disponibilidade",
        {"data": "2026-09-19", "num_pessoas": 2, "horario": "23:00"},
        "HORARIO_FORA_DE_SERVICO",
    ),
    (
        "consultar_disponibilidade",
        {"data": "19/09/2026", "num_pessoas": 2},
        "FORMATO_DATA_INVALIDO",
    ),
    (
        "consultar_disponibilidade",
        {"data": "2026-09-19", "num_pessoas": 2, "horario": "20:15"},
        "FORMATO_HORARIO_INVALIDO",
    ),
    (
        "criar_reserva",
        RESERVA | {"data": "2026-09-19", "horario": "20:00", "num_pessoas": 6},
        "SEM_DISPONIBILIDADE",
    ),
    ("criar_reserva", RESERVA | {"num_pessoas": 13}, "GRUPO_ACIMA_DO_LIMITE"),
    ("criar_reserva", RESERVA | {"data": "2026-09-21", "horario": "20:00"}, "DIA_FECHADO"),
    ("criar_reserva", RESERVA | {"horario": "16:00"}, "HORARIO_FORA_DE_SERVICO"),
    ("criar_reserva", RESERVA | {"data": "2026-11-20"}, "FORA_DA_JANELA"),
    ("criar_reserva", RESERVA | {"data": "amanhã"}, "FORMATO_DATA_INVALIDO"),
    ("criar_reserva", RESERVA | {"horario": "19h"}, "FORMATO_HORARIO_INVALIDO"),
    ("consultar_reserva", {"codigo": "ZZZZZZ"}, "RESERVA_NAO_ENCONTRADA"),
    ("cancelar_reserva", {"codigo": "ZZZZZZ"}, "RESERVA_NAO_ENCONTRADA"),
    ("cancelar_reserva", {"codigo": "W4X9HT"}, "JA_CANCELADA"),
    ("listar_pratos_do_dia", {"data": "10/11/2026"}, "FORMATO_DATA_INVALIDO"),
    ("ferramenta_inventada", {}, "TOOL_DESCONHECIDA"),
]


@pytest.mark.parametrize(("name", "args", "code"), ERROR_SCENARIOS)
def test_codigo_de_erro(registry: ToolRegistry, name: str, args: dict[str, Any], code: str) -> None:
    result = registry.dispatch(name, args)

    assert error_code(result) == code
    assert json.loads(result.to_json())["error"]["code"] == code


def test_cenarios_cobrem_todos_os_codigos_de_dominio() -> None:
    def codes(cls: type[DomainError]) -> set[str]:
        own = {cls.CODE} if hasattr(cls, "CODE") else set()
        return own.union(*(codes(sub) for sub in cls.__subclasses__()))

    assert codes(DomainError) <= {code for _, _, code in ERROR_SCENARIOS}
    assert len(codes(DomainError)) == 10


# Robustez do registry

GARBAGE: list[object] = [
    None,
    [],
    "texto solto",
    42,
    {"data": {"aninhado": True}},
    {"num_pessoas": None, "data": None},
    {"codigo": 123},
    {"pergunta": "x" * 5000},
    {"data": "2026-09-19", "num_pessoas": 10**9, "horario": "99:99"},
    {"nome": ["lista"], "telefone": {}, "data": 1.5},
]


@pytest.mark.parametrize("args", GARBAGE)
@pytest.mark.parametrize(
    "name",
    [
        "buscar_conhecimento",
        "consultar_disponibilidade",
        "criar_reserva",
        "consultar_reserva",
        "cancelar_reserva",
        "listar_pratos_do_dia",
    ],
)
def test_dispatch_nunca_levanta(registry: ToolRegistry, name: str, args: object) -> None:
    result = registry.dispatch(name, args)

    assert isinstance(result, ToolResult)
    json.loads(result.to_json())


class _Vazio(BaseModel):
    pass


def _explode(_: _Vazio) -> dict[str, Any]:
    raise RuntimeError("segredo interno /caminho/arquivo.py")


def test_excecao_inesperada_vira_erro_interno_sem_detalhes(registry: ToolRegistry) -> None:
    registry.register(Tool("quebrada", "Sempre falha.", _Vazio, _explode))

    result = registry.dispatch("quebrada", {})
    payload = result.to_json()

    assert error_code(result) == "ERRO_INTERNO"
    assert "segredo" not in payload
    assert "Traceback" not in payload


def test_observador_recebe_cada_chamada(registry: ToolRegistry) -> None:
    recorder = registry.observer
    assert isinstance(recorder, Recorder)

    registry.dispatch("listar_pratos_do_dia", {})
    registry.dispatch("ferramenta_inventada", {"x": 1})

    assert [(name, result.ok) for name, _, result, _ in recorder.calls] == [
        ("listar_pratos_do_dia", True),
        ("ferramenta_inventada", False),
    ]
    assert all(duration >= 0 for *_, duration in recorder.calls)


def test_observador_com_falha_nao_afeta_o_resultado(registry: ToolRegistry) -> None:
    class Broken:
        def on_tool_call(self, *_: object) -> None:
            raise RuntimeError("falha no trace")

    registry.observer = Broken()

    assert registry.dispatch("listar_pratos_do_dia", {}).ok


def test_registro_duplicado(registry: ToolRegistry) -> None:
    with pytest.raises(ValueError, match="já registrada"):
        registry.register(Tool("listar_pratos_do_dia", "", _Vazio, _explode))


def test_envelope_serializa_acentos_sem_escape() -> None:
    assert (
        ToolResult.success({"dia": "sábado"}).to_json() == '{"ok": true, "data": {"dia": "sábado"}}'
    )
