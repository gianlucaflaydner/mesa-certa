from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from mesa_certa.domain import date_resolver as dr
from mesa_certa.domain.errors import InvalidDateFormat, InvalidTimeFormat

SP = ZoneInfo("America/Sao_Paulo")
NOW = datetime(2026, 9, 15, 14, 0, tzinfo=SP)


def test_parse_date_iso() -> None:
    assert dr.parse_date("2026-09-19") == date(2026, 9, 19)


@pytest.mark.parametrize(
    "value",
    ["19/09/2026", "2026-9-19", "20260919", "2026-02-30", "sábado", "", "2026-09-19T20:00"],
)
def test_parse_date_rejeita_formatos(value: str) -> None:
    with pytest.raises(InvalidDateFormat) as exc:
        dr.parse_date(value)
    assert exc.value.code == "FORMATO_DATA_INVALIDO"
    assert exc.value.details == {"valor": value}


@pytest.mark.parametrize(
    ("value", "expected"),
    [("20:00", time(20, 0)), ("00:00", time(0, 0)), ("23:30", time(23, 30))],
)
def test_parse_time_em_slot(value: str, expected: time) -> None:
    assert dr.parse_time(value) == expected


@pytest.mark.parametrize("value", ["20:15", "8:00", "24:00", "20h", "20:00:00", "", "19:45"])
def test_parse_time_rejeita_formatos(value: str) -> None:
    with pytest.raises(InvalidTimeFormat) as exc:
        dr.parse_time(value)
    assert exc.value.code == "FORMATO_HORARIO_INVALIDO"


def test_formatacao() -> None:
    assert dr.format_date(date(2026, 9, 5)) == "2026-09-05"
    assert dr.format_time(time(9, 30)) == "09:30"


def test_weekday_segunda_e_zero() -> None:
    assert dr.weekday_of(date(2026, 9, 21)) == 0
    assert dr.weekday_of(date(2026, 9, 20)) == 6


def test_virada_da_meia_noite() -> None:
    assert dr.minutes_since_midnight(time(0, 0)) == 0
    assert dr.minutes_since_midnight(time(0, 0), crosses_midnight=True) == 1440
    assert dr.span_minutes(time(22, 30), time(0, 30)) == (1350, 1470)
    assert dr.span_minutes(time(18, 0), time(0, 0)) == (1080, 1440)
    assert dr.span_minutes(time(19, 30), time(21, 30)) == (1170, 1290)
    assert dr.time_from_minutes(1470) == time(0, 30)
    assert dr.add_duration(date(2026, 9, 19), time(22, 30), 120) == (date(2026, 9, 20), time(0, 30))


@pytest.mark.parametrize(
    ("day", "at", "expected"),
    [
        (date(2026, 9, 15), time(15, 0), True),  # exatamente 60 min
        (date(2026, 9, 15), time(14, 30), False),  # 30 min
        (date(2026, 9, 15), time(13, 30), False),  # passado
        (date(2026, 11, 14), time(14, 0), True),  # exatamente 60 dias
        (date(2026, 11, 14), time(14, 30), False),  # 60 dias e 30 min
    ],
)
def test_janela_de_reserva_nos_limites(day: date, at: time, expected: bool) -> None:
    assert dr.is_within_booking_window(day, at, NOW) is expected


def test_janela_59_minutos_e_recusada() -> None:
    assert dr.booking_advance(date(2026, 9, 15), time(15, 0), NOW + timedelta(minutes=1)) == (
        timedelta(minutes=59)
    )
    assert not dr.is_within_booking_window(
        date(2026, 9, 15), time(15, 0), NOW + timedelta(minutes=1)
    )


def test_intervalo_de_datas_reservaveis() -> None:
    assert dr.booking_date_range(NOW) == (date(2026, 9, 15), date(2026, 11, 14))
    late = datetime(2026, 9, 15, 23, 30, tzinfo=SP)
    assert dr.booking_date_range(late)[0] == date(2026, 9, 16)


def test_relogios() -> None:
    fixed = dr.FixedClock(NOW)
    assert fixed.now() == NOW

    system_now = dr.SystemClock(SP).now()
    assert system_now.tzinfo is SP
    assert dr.localize(date(2026, 9, 19), time(20, 0), NOW).tzinfo is SP
