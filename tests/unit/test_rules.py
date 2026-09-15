from datetime import date, timedelta

import pytest

from mesa_certa.domain import rules
from mesa_certa.domain.errors import (
    DayClosed,
    GroupTooLarge,
    InvalidGroupSize,
    OutsideBookingWindow,
    OutsideServiceHours,
)
from mesa_certa.domain.rules import Service, ServiceWindow, TableInfo, Zone

SAT_LUNCH = ServiceWindow(Service.ALMOCO, 12 * 60, 15 * 60)
SAT_DINNER = ServiceWindow(Service.JANTAR, 18 * 60, 24 * 60)
SATURDAY = date(2026, 9, 19)
MONDAY = date(2026, 9, 21)

TABLES = [
    *(TableInfo(i, f"S{i}", Zone.SALAO, 4, False) for i in range(1, 9)),
    *(TableInfo(8 + i, f"V{i}", Zone.VARANDA, 2, False) for i in range(1, 5)),
    *(TableInfo(12 + i, f"M{i}", Zone.MEZANINO, 6, True) for i in range(1, 5)),
]
SALAO_IDS = set(range(1, 9))
VARANDA_IDS = set(range(9, 13))
MEZANINO_IDS = set(range(13, 17))


def labels(allocation: list[TableInfo] | None) -> list[str] | None:
    return None if allocation is None else [t.label for t in allocation]


@pytest.mark.parametrize("size", [1, 12])
def test_grupo_nos_limites_e_aceito(size: int) -> None:
    rules.validate_party_size(size)


def test_grupo_zero_e_invalido() -> None:
    with pytest.raises(InvalidGroupSize) as exc:
        rules.validate_party_size(0)
    assert exc.value.code == "GRUPO_INVALIDO"


def test_grupo_13_acima_do_limite() -> None:
    with pytest.raises(GroupTooLarge) as exc:
        rules.validate_party_size(13)
    assert exc.value.code == "GRUPO_ACIMA_DO_LIMITE"
    assert exc.value.details == {
        "maximo": 12,
        "informado": 13,
        "contato_eventos": "(51) 3030-4050",
    }


def test_antecedencia() -> None:
    rules.validate_advance(timedelta(minutes=60))
    rules.validate_advance(timedelta(days=60))
    for invalid in (timedelta(minutes=59), timedelta(days=60, minutes=1), timedelta(hours=-1)):
        with pytest.raises(OutsideBookingWindow):
            rules.validate_advance(invalid)


def test_segunda_e_fechada_mesmo_com_servico() -> None:
    assert rules.closed_reason(MONDAY, [SAT_DINNER], None) == "Fechado às segundas-feiras"


def test_fechamento_cadastrado() -> None:
    assert rules.closed_reason(SATURDAY, [SAT_DINNER], "Natal") == "Natal"


def test_dia_sem_servico_e_fechado() -> None:
    assert rules.closed_reason(SATURDAY, [], None) == "Sem serviço neste dia"


def test_dia_aberto() -> None:
    assert rules.closed_reason(SATURDAY, [SAT_LUNCH, SAT_DINNER], None) is None
    rules.ensure_open(SATURDAY, [SAT_DINNER], None)


def test_ensure_open_informa_proxima_data() -> None:
    with pytest.raises(DayClosed) as exc:
        rules.ensure_open(MONDAY, [], None, next_open=date(2026, 9, 22))
    assert exc.value.details == {
        "motivo": "Fechado às segundas-feiras",
        "proxima_data_aberta": "2026-09-22",
    }


def test_slots_do_jantar_que_fecha_a_meia_noite() -> None:
    slots = SAT_DINNER.slots()
    assert slots[0] == 18 * 60
    assert slots[-1] == 22 * 60 + 30
    assert SAT_DINNER.contains_slot(22 * 60 + 30)
    assert not SAT_DINNER.contains_slot(23 * 60)
    assert not SAT_DINNER.contains_slot(18 * 60 + 15)


def test_ultimo_slot_do_almoco() -> None:
    assert SAT_LUNCH.slots()[-1] == 13 * 60 + 30


@pytest.mark.parametrize("start", [23 * 60, 16 * 60, 11 * 60 + 30, 14 * 60])
def test_slot_fora_do_servico(start: int) -> None:
    with pytest.raises(OutsideServiceHours) as exc:
        rules.service_for_slot(start, [SAT_LUNCH, SAT_DINNER])
    assert exc.value.code == "HORARIO_FORA_DE_SERVICO"


def test_slot_dentro_do_servico() -> None:
    assert rules.service_for_slot(20 * 60, [SAT_LUNCH, SAT_DINNER]) is SAT_DINNER
    assert rules.service_for_slot(12 * 60, [SAT_LUNCH, SAT_DINNER]) is SAT_LUNCH


@pytest.mark.parametrize(("size", "minutes"), [(1, 90), (4, 90), (5, 120), (12, 120)])
def test_duracao_por_grupo(size: int, minutes: int) -> None:
    assert rules.stay_minutes(size) == minutes


def test_sobreposicao() -> None:
    assert rules.overlaps(1200, 1320, 1170, 1290)
    assert not rules.overlaps(1290, 1410, 1170, 1290)  # começa quando a outra termina
    assert not rules.overlaps(1050, 1170, 1170, 1290)


@pytest.mark.parametrize(
    ("size", "busy", "expected"),
    [
        (2, set(), ["V1"]),
        (1, {9}, ["V2"]),
        (2, VARANDA_IDS, ["S1"]),
        (2, VARANDA_IDS | SALAO_IDS, None),
        (3, set(), ["S1"]),
        (4, SALAO_IDS, ["M1"]),
        (6, set(), ["M1"]),
        (5, MEZANINO_IDS, None),
        (7, set(), ["M1", "M2"]),
        (12, {13, 15}, ["M2", "M4"]),
        (7, {13, 14, 15}, None),
    ],
)
def test_alocacao(size: int, busy: set[int], expected: list[str] | None) -> None:
    assert labels(rules.allocate_tables(TABLES, busy, size)) == expected


def test_alocacao_recusa_grupo_13() -> None:
    with pytest.raises(GroupTooLarge):
        rules.allocate_tables(TABLES, set(), 13)


def test_mesas_necessarias() -> None:
    assert rules.tables_needed(6) == 1
    assert rules.tables_needed(7) == 2


def test_cancelamento_sem_onus() -> None:
    assert rules.is_free_cancellation(timedelta(hours=4))
    assert rules.is_free_cancellation(timedelta(hours=4, minutes=1))
    assert not rules.is_free_cancellation(timedelta(hours=3, minutes=59))
