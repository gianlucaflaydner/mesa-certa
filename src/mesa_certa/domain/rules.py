"""Constantes do PRD §4.4 e validações puras das regras RN-01 a RN-06.

Nada aqui lê banco ou relógio: tudo chega por parâmetro.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from mesa_certa.domain.errors import (
    DayClosed,
    GroupTooLarge,
    InvalidGroupSize,
    OutsideBookingWindow,
    OutsideServiceHours,
)

SLOT_MINUTES = 30
LAST_BOOKING_BEFORE_CLOSE_MINUTES = 90
SHORT_STAY_MINUTES = 90
LONG_STAY_MINUTES = 120
LONG_STAY_FROM_PARTY_SIZE = 5
COMBINED_TABLES_FROM_PARTY_SIZE = 7
MIN_ADVANCE = timedelta(minutes=60)
MAX_ADVANCE = timedelta(days=60)
MIN_PARTY_SIZE = 1
MAX_PARTY_SIZE = 12
LATE_TOLERANCE_MINUTES = 20
FREE_CANCELLATION_NOTICE = timedelta(hours=4)
MAX_ALTERNATIVES = 4
MONDAY = 0


class Zone(StrEnum):
    SALAO = "salao"
    VARANDA = "varanda"
    MEZANINO = "mezanino"
    BALCAO = "balcao"


class Service(StrEnum):
    ALMOCO = "almoco"
    JANTAR = "jantar"


class ReservationStatus(StrEnum):
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"
    CONCLUIDA = "CONCLUIDA"
    NO_SHOW = "NO_SHOW"


@dataclass(frozen=True)
class ServiceWindow:
    """Serviço de um dia, em minutos desde a meia-noite (fechamento já com +1440 se vira o dia)."""

    service: Service
    opens_min: int
    closes_min: int

    @property
    def last_slot_min(self) -> int:
        return self.closes_min - LAST_BOOKING_BEFORE_CLOSE_MINUTES

    def slots(self) -> list[int]:
        return list(range(self.opens_min, self.last_slot_min + 1, SLOT_MINUTES))

    def contains_slot(self, start_min: int) -> bool:
        return (
            self.opens_min <= start_min <= self.last_slot_min
            and (start_min - self.opens_min) % SLOT_MINUTES == 0
        )


@dataclass(frozen=True)
class TableInfo:
    id: int
    label: str
    zone: Zone
    capacity: int
    combinable: bool


# RN-01
def validate_party_size(party_size: int) -> None:
    if party_size < MIN_PARTY_SIZE:
        raise InvalidGroupSize(details={"minimo": MIN_PARTY_SIZE, "informado": party_size})
    if party_size > MAX_PARTY_SIZE:
        raise GroupTooLarge(details={"maximo": MAX_PARTY_SIZE, "informado": party_size})


# RN-02
def is_advance_allowed(advance: timedelta) -> bool:
    return MIN_ADVANCE <= advance <= MAX_ADVANCE


def validate_advance(advance: timedelta) -> None:
    if not is_advance_allowed(advance):
        raise OutsideBookingWindow(
            details={
                "antecedencia_minima_minutos": int(MIN_ADVANCE.total_seconds() // 60),
                "antecedencia_maxima_dias": MAX_ADVANCE.days,
            }
        )


# RN-03
def closed_reason(
    day: date, services: Sequence[ServiceWindow], closure_reason: str | None
) -> str | None:
    if closure_reason is not None:
        return closure_reason
    if day.weekday() == MONDAY:
        return "Fechado às segundas-feiras"
    if not services:
        return "Sem serviço neste dia"
    return None


def ensure_open(
    day: date,
    services: Sequence[ServiceWindow],
    closure_reason: str | None,
    next_open: date | None = None,
) -> None:
    reason = closed_reason(day, services, closure_reason)
    if reason is not None:
        raise DayClosed(
            details={
                "motivo": reason,
                "proxima_data_aberta": next_open.isoformat() if next_open else None,
            }
        )


# RN-04
def service_for_slot(start_min: int, services: Sequence[ServiceWindow]) -> ServiceWindow:
    for window in services:
        if window.contains_slot(start_min):
            return window
    raise OutsideServiceHours(
        details={"servicos": [{"servico": w.service.value} for w in services]}
    )


# RN-06
def stay_minutes(party_size: int) -> int:
    return LONG_STAY_MINUTES if party_size >= LONG_STAY_FROM_PARTY_SIZE else SHORT_STAY_MINUTES


def overlaps(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return start_a < end_b and end_a > start_b


# RN-05
_ZONES_BY_PARTY_SIZE: tuple[tuple[int, tuple[Zone, ...]], ...] = (
    (2, (Zone.VARANDA, Zone.SALAO)),
    (4, (Zone.SALAO, Zone.MEZANINO)),
    (6, (Zone.MEZANINO,)),
)


def tables_needed(party_size: int) -> int:
    return 2 if party_size >= COMBINED_TABLES_FROM_PARTY_SIZE else 1


def allocate_tables(
    tables: Sequence[TableInfo], busy_ids: Collection[int], party_size: int
) -> list[TableInfo] | None:
    """Menor capacidade suficiente, desempate por menor id (SDD §5.6)."""
    validate_party_size(party_size)
    free = sorted((t for t in tables if t.id not in busy_ids), key=lambda t: (t.capacity, t.id))

    if party_size >= COMBINED_TABLES_FROM_PARTY_SIZE:
        pool = sorted(
            (t for t in free if t.zone is Zone.MEZANINO and t.combinable), key=lambda t: t.id
        )
        pair = pool[:2]
        if len(pair) == 2 and sum(t.capacity for t in pair) >= party_size:
            return pair
        return None

    zones = next(z for limit, z in _ZONES_BY_PARTY_SIZE if party_size <= limit)
    for table in free:
        if table.zone in zones and table.capacity >= party_size:
            return [table]
    return None


# RN-13
def is_free_cancellation(advance: timedelta) -> bool:
    return advance >= FREE_CANCELLATION_NOTICE
