"""Consulta de disponibilidade (SDD §5.3).

As funções `load_*` e `find_tables` também servem ao `ReservationService`, que revalida
tudo dentro da própria transação.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from mesa_certa.db.models import Closure, DiningTable, Reservation, ServiceHour
from mesa_certa.domain import date_resolver as dr
from mesa_certa.domain import rules
from mesa_certa.domain.rules import ReservationStatus, Service, ServiceWindow, TableInfo, Zone


@dataclass(frozen=True)
class SlotAvailability:
    date: date
    time: time | None
    available: bool
    zone: Zone | None  # zona da mesa alocável, se disponível
    tables_needed: int


@dataclass(frozen=True)
class AvailabilityResult:
    requested: SlotAvailability
    alternatives: list[SlotAvailability]
    closed_reason: str | None  # preenchido quando o dia não abre
    next_open_date: date | None = None


@dataclass(frozen=True)
class Booking:
    start_min: int
    end_min: int
    table_ids: frozenset[int]


@dataclass(frozen=True)
class Calendar:
    services_by_weekday: dict[int, list[ServiceWindow]]
    closures: dict[date, str]

    def services_on(self, day: date) -> list[ServiceWindow]:
        return self.services_by_weekday.get(dr.weekday_of(day), [])

    def closed_reason(self, day: date) -> str | None:
        return rules.closed_reason(day, self.services_on(day), self.closures.get(day))

    def next_open_date(self, after: date) -> date | None:
        for offset in range(1, rules.MAX_ADVANCE.days + 1):
            candidate = after + timedelta(days=offset)
            if self.closed_reason(candidate) is None:
                return candidate
        return None


def load_calendar(session: Session) -> Calendar:
    services: dict[int, list[ServiceWindow]] = {}
    for row in session.scalars(select(ServiceHour).order_by(ServiceHour.opens_at)):
        opens = dr.parse_time(row.opens_at)
        opens_min, closes_min = dr.span_minutes(opens, dr.parse_time(row.closes_at))
        services.setdefault(row.weekday, []).append(
            ServiceWindow(Service(row.service), opens_min, closes_min)
        )
    closures = {
        dr.parse_date(row.closure_date): row.reason for row in session.scalars(select(Closure))
    }
    return Calendar(services, closures)


def load_tables(session: Session) -> list[TableInfo]:
    rows = session.scalars(
        select(DiningTable).where(DiningTable.reservable.is_(True)).order_by(DiningTable.id)
    )
    return [TableInfo(t.id, t.label, Zone(t.zone), t.capacity, t.combinable) for t in rows]


def load_bookings(session: Session, day: date) -> list[Booking]:
    """Reservas confirmadas do dia. Nenhum serviço começa antes do fim de uma virada."""
    rows = session.scalars(
        select(Reservation)
        .where(
            Reservation.reservation_date == dr.format_date(day),
            Reservation.status == ReservationStatus.CONFIRMADA.value,
        )
        .options(selectinload(Reservation.tables))
    )
    bookings = []
    for row in rows:
        start_min, end_min = dr.span_minutes(
            dr.parse_time(row.start_time), dr.parse_time(row.end_time)
        )
        bookings.append(Booking(start_min, end_min, frozenset(t.id for t in row.tables)))
    return bookings


def find_tables(
    tables: Sequence[TableInfo], bookings: Sequence[Booking], start_min: int, party_size: int
) -> list[TableInfo] | None:
    end_min = start_min + rules.stay_minutes(party_size)
    busy = {
        table_id
        for b in bookings
        if rules.overlaps(start_min, end_min, b.start_min, b.end_min)
        for table_id in b.table_ids
    }
    return rules.allocate_tables(tables, busy, party_size)


class AvailabilityService:
    def __init__(self, session_factory: sessionmaker[Session], clock: dr.Clock) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def check(self, day: date, party_size: int, at: time | None = None) -> AvailabilityResult:
        rules.validate_party_size(party_size)
        current = self._clock.now()
        if at is not None:
            rules.validate_advance(dr.booking_advance(day, at, current))
        else:
            first, last = dr.booking_date_range(current)
            if not first <= day <= last:
                rules.validate_advance(dr.booking_advance(day, time(0, 0), current))

        with self._session_factory() as session:
            calendar = load_calendar(session)
            reason = calendar.closed_reason(day)
            if reason is not None:
                return AvailabilityResult(
                    requested=SlotAvailability(day, at, False, None, 0),
                    alternatives=[],
                    closed_reason=reason,
                    next_open_date=calendar.next_open_date(day),
                )

            services = calendar.services_on(day)
            tables = load_tables(session)
            bookings = load_bookings(session, day)

        def evaluate(start_min: int) -> SlotAvailability:
            allocation = find_tables(tables, bookings, start_min, party_size)
            return SlotAvailability(
                date=day,
                time=dr.time_from_minutes(start_min),
                available=allocation is not None,
                zone=allocation[0].zone if allocation else None,
                tables_needed=len(allocation) if allocation else rules.tables_needed(party_size),
            )

        def bookable(start_min: int) -> bool:
            return dr.is_within_booking_window(day, dr.time_from_minutes(start_min), current)

        if at is None:
            slots = sorted(s for w in services for s in w.slots())
            free = [slot for s in slots if bookable(s) and (slot := evaluate(s)).available]
            return AvailabilityResult(
                requested=SlotAvailability(day, None, False, None, rules.tables_needed(party_size)),
                alternatives=free,
                closed_reason=None,
            )

        requested_min = dr.minutes_since_midnight(at)
        window = rules.service_for_slot(requested_min, services)
        candidates = sorted(
            (s for s in window.slots() if s != requested_min and bookable(s)),
            key=lambda s: (abs(s - requested_min), s),
        )
        alternatives: list[SlotAvailability] = []
        for start_min in candidates:
            slot = evaluate(start_min)
            if slot.available:
                alternatives.append(slot)
                if len(alternatives) == rules.MAX_ALTERNATIVES:
                    break

        return AvailabilityResult(
            requested=evaluate(requested_min),
            alternatives=alternatives,
            closed_reason=None,
        )
