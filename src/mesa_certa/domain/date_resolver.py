"""Normalização de data e horário (SDD §5.5, ADR-005).

`now()` é o único ponto do sistema que lê o relógio. Os serviços recebem um `Clock`.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from typing import Protocol

from mesa_certa.domain import rules
from mesa_certa.domain.errors import InvalidDateFormat, InvalidTimeFormat

MINUTES_PER_DAY = 24 * 60
WEEKDAY_NAMES = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TIME_RE = re.compile(r"([01]\d|2[0-3]):(00|30)")


def now(tz: tzinfo) -> datetime:
    return datetime.now(tz)


class Clock(Protocol):
    def now(self) -> datetime: ...


@dataclass(frozen=True)
class SystemClock:
    tz: tzinfo

    def now(self) -> datetime:
        return now(self.tz)


@dataclass
class FixedClock:
    """Relógio parado, para testes e para o runner de avaliação."""

    instant: datetime

    def now(self) -> datetime:
        return self.instant


def parse_date(value: str) -> date:
    if not _DATE_RE.fullmatch(value):
        raise InvalidDateFormat(details={"valor": value})
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InvalidDateFormat(details={"valor": value}) from exc


def parse_time(value: str) -> time:
    match = _TIME_RE.fullmatch(value)
    if match is None:
        raise InvalidTimeFormat(details={"valor": value})
    return time(int(match.group(1)), int(match.group(2)))


def format_date(value: date) -> str:
    return value.isoformat()


def format_time(value: time) -> str:
    return value.strftime("%H:%M")


def weekday_of(value: date) -> int:
    return value.weekday()


def weekday_name(value: date) -> str:
    return WEEKDAY_NAMES[value.weekday()]


def minutes_since_midnight(value: time, crosses_midnight: bool = False) -> int:
    minutes = value.hour * 60 + value.minute
    return minutes + MINUTES_PER_DAY if crosses_midnight else minutes


def time_from_minutes(minutes: int) -> time:
    minutes %= MINUTES_PER_DAY
    return time(minutes // 60, minutes % 60)


def span_minutes(start: time, end: time) -> tuple[int, int]:
    """Início e fim em minutos; fim menor ou igual ao início significa virada do dia."""
    start_min = minutes_since_midnight(start)
    end_min = minutes_since_midnight(end)
    if end_min <= start_min:
        end_min += MINUTES_PER_DAY
    return start_min, end_min


def add_duration(day: date, start: time, minutes: int) -> tuple[date, time]:
    end = datetime.combine(day, start) + timedelta(minutes=minutes)
    return end.date(), end.time()


def localize(day: date, start: time, reference: datetime) -> datetime:
    return datetime.combine(day, start, tzinfo=reference.tzinfo)


def booking_advance(day: date, start: time, current: datetime) -> timedelta:
    return localize(day, start, current) - current


def is_within_booking_window(day: date, start: time, current: datetime) -> bool:
    return rules.is_advance_allowed(booking_advance(day, start, current))


def booking_date_range(current: datetime) -> tuple[date, date]:
    """Primeira e última data em que algum horário pode cair na janela da RN-02."""
    return (current + rules.MIN_ADVANCE).date(), (current + rules.MAX_ADVANCE).date()
