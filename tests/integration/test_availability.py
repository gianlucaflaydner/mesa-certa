from datetime import date, time

import pytest

from mesa_certa.domain.availability import AvailabilityResult, AvailabilityService
from mesa_certa.domain.date_resolver import FixedClock
from mesa_certa.domain.errors import (
    GroupTooLarge,
    InvalidGroupSize,
    OutsideBookingWindow,
    OutsideServiceHours,
)
from mesa_certa.domain.rules import Zone
from tests.integration.conftest import at

SAT_19 = date(2026, 9, 19)


def times(result: AvailabilityResult) -> list[str]:
    return [s.time.strftime("%H:%M") for s in result.alternatives if s.time]


def test_tool_001_dois_no_sabado_as_20(availability: AvailabilityService) -> None:
    result = availability.check(SAT_19, 2, time(20, 0))

    assert result.requested.available
    assert result.requested.zone is Zone.VARANDA
    assert result.closed_reason is None


def test_tool_004_seis_no_sabado_lotado(availability: AvailabilityService) -> None:
    result = availability.check(SAT_19, 6, time(20, 0))

    assert not result.requested.available
    assert result.requested.zone is None
    assert times(result) == ["21:30", "22:00", "22:30"]
    assert all(s.zone is Zone.MEZANINO for s in result.alternatives)


def test_tool_002_horarios_livres_sem_horario(availability: AvailabilityService) -> None:
    result = availability.check(date(2026, 9, 16), 3)

    assert not result.requested.available
    assert result.requested.time is None
    assert times(result) == [
        "18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00", "21:30",
    ]  # fmt: skip


def test_alternativas_por_proximidade_no_maximo_4(availability: AvailabilityService) -> None:
    result = availability.check(SAT_19, 2, time(20, 0))

    assert times(result) == ["19:30", "20:30", "19:00", "21:00"]


def test_alternativas_ficam_no_mesmo_servico(availability: AvailabilityService) -> None:
    result = availability.check(SAT_19, 2, time(12, 0))

    assert times(result) == ["12:30", "13:00", "13:30"]


def test_sem_horario_filtra_slots_dentro_de_60_min(
    availability: AvailabilityService, clock: FixedClock
) -> None:
    clock.instant = at(2026, 9, 18, 18, 10)

    result = availability.check(date(2026, 9, 18), 2)

    assert times(result)[0] == "19:30"


def test_segunda_fechada_com_proxima_data(availability: AvailabilityService) -> None:
    result = availability.check(date(2026, 9, 21), 4, time(20, 0))

    assert result.closed_reason == "Fechado às segundas-feiras"
    assert result.next_open_date == date(2026, 9, 22)
    assert not result.requested.available
    assert result.alternatives == []


def test_fechamento_cadastrado(availability: AvailabilityService) -> None:
    result = availability.check(date(2026, 10, 14), 2)

    assert result.closed_reason == "Manutenção da cozinha"
    assert result.next_open_date == date(2026, 10, 15)


def test_jantar_de_sabado_aceita_2230(availability: AvailabilityService) -> None:
    assert availability.check(SAT_19, 2, time(22, 30)).requested.available


def test_jantar_de_sabado_recusa_2300(availability: AvailabilityService) -> None:
    with pytest.raises(OutsideServiceHours):
        availability.check(SAT_19, 2, time(23, 0))


def test_horario_fora_de_servico_em_dia_so_de_jantar(availability: AvailabilityService) -> None:
    with pytest.raises(OutsideServiceHours):
        availability.check(date(2026, 9, 16), 2, time(12, 0))


def test_grupo_de_7_une_duas_mesas_do_mezanino(
    availability: AvailabilityService, clock: FixedClock
) -> None:
    clock.instant = at(2026, 9, 22, 14)

    result = availability.check(date(2026, 9, 26), 7, time(20, 0))

    assert result.requested.available
    assert result.requested.tables_needed == 2
    assert result.requested.zone is Zone.MEZANINO


@pytest.mark.parametrize("size", [13, 18])
def test_grupo_acima_do_limite(availability: AvailabilityService, size: int) -> None:
    with pytest.raises(GroupTooLarge):
        availability.check(SAT_19, size, time(20, 0))


def test_grupo_zero(availability: AvailabilityService) -> None:
    with pytest.raises(InvalidGroupSize):
        availability.check(SAT_19, 0)


@pytest.mark.parametrize(
    ("day", "at_time"),
    [
        (date(2026, 9, 15), time(14, 30)),
        (date(2026, 9, 12), time(20, 0)),
        (date(2026, 9, 12), None),
        (date(2026, 11, 20), None),
        (date(2026, 11, 20), time(20, 0)),
    ],
)
def test_fora_da_janela(availability: AvailabilityService, day: date, at_time: time | None) -> None:
    with pytest.raises(OutsideBookingWindow):
        availability.check(day, 2, at_time)
