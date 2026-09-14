"""Criação, consulta e cancelamento de reservas (SDD §5.4)."""

import random
from dataclasses import dataclass
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from mesa_certa.db.models import DiningTable, Reservation
from mesa_certa.db.session import write_transaction
from mesa_certa.domain import codes, rules
from mesa_certa.domain import date_resolver as dr
from mesa_certa.domain.availability import find_tables, load_bookings, load_calendar, load_tables
from mesa_certa.domain.errors import AlreadyCancelled, NoAvailability, ReservationNotFound
from mesa_certa.domain.rules import ReservationStatus, Zone


@dataclass(frozen=True)
class CreateReservationCommand:
    name: str
    phone: str
    party_size: int
    date: date
    time: time
    email: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class ReservationDetails:
    code: str
    customer_name: str
    customer_phone: str
    customer_email: str | None
    party_size: int
    date: date
    start_time: time
    end_time: time
    status: ReservationStatus
    zone: Zone | None
    table_labels: tuple[str, ...]
    notes: str | None
    starts_at: datetime
    free_cancellation_until: datetime
    late_tolerance_minutes: int
    cancelled_at: datetime | None
    cancellation_reason: str | None


@dataclass(frozen=True)
class CancellationResult:
    code: str
    status: ReservationStatus
    within_free_window: bool
    cancelled_at: datetime


class ReservationService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        clock: dr.Clock,
        rng: random.Random | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._rng = rng

    def create(self, cmd: CreateReservationCommand) -> ReservationDetails:
        # A consulta anterior pode estar obsoleta (R-04): tudo é revalidado aqui.
        rules.validate_party_size(cmd.party_size)
        current = self._clock.now()
        rules.validate_advance(dr.booking_advance(cmd.date, cmd.time, current))
        start_min = dr.minutes_since_midnight(cmd.time)

        with write_transaction(self._session_factory) as session:
            calendar = load_calendar(session)
            services = calendar.services_on(cmd.date)
            rules.ensure_open(
                cmd.date,
                services,
                calendar.closures.get(cmd.date),
                next_open=calendar.next_open_date(cmd.date),
            )
            rules.service_for_slot(start_min, services)

            allocation = find_tables(
                load_tables(session), load_bookings(session, cmd.date), start_min, cmd.party_size
            )
            if allocation is None:
                raise NoAvailability(
                    details={
                        "data": dr.format_date(cmd.date),
                        "horario": dr.format_time(cmd.time),
                        "num_pessoas": cmd.party_size,
                    }
                )

            code = codes.generate_unique_code(
                lambda candidate: _find(session, candidate) is not None, self._rng
            )
            _, end = dr.add_duration(cmd.date, cmd.time, rules.stay_minutes(cmd.party_size))
            stamp = current.isoformat(timespec="seconds")
            row = Reservation(
                code=code,
                customer_name=cmd.name,
                customer_phone=cmd.phone,
                customer_email=cmd.email,
                party_size=cmd.party_size,
                reservation_date=dr.format_date(cmd.date),
                start_time=dr.format_time(cmd.time),
                end_time=dr.format_time(end),
                status=ReservationStatus.CONFIRMADA.value,
                notes=cmd.notes,
                created_at=stamp,
                updated_at=stamp,
                tables=[session.get_one(DiningTable, t.id) for t in allocation],
            )
            session.add(row)
            session.flush()
            return _to_details(row, current)

    def get_by_code(self, code: str) -> ReservationDetails | None:
        with self._session_factory() as session:
            row = _find(session, codes.normalize_code(code))
            return _to_details(row, self._clock.now()) if row else None

    def cancel(self, code: str, reason: str | None = None) -> CancellationResult:
        normalized = codes.normalize_code(code)
        with write_transaction(self._session_factory) as session:
            row = _find(session, normalized)
            if row is None:
                raise ReservationNotFound(details={"codigo": normalized})
            if row.status != ReservationStatus.CONFIRMADA:
                raise AlreadyCancelled(details={"codigo": normalized, "situacao": row.status})

            current = self._clock.now()
            advance = dr.booking_advance(
                dr.parse_date(row.reservation_date), dr.parse_time(row.start_time), current
            )
            stamp = current.isoformat(timespec="seconds")
            row.status = ReservationStatus.CANCELADA.value
            row.cancelled_at = stamp
            row.cancellation_reason = reason
            row.updated_at = stamp
            return CancellationResult(
                code=normalized,
                status=ReservationStatus.CANCELADA,
                within_free_window=rules.is_free_cancellation(advance),
                cancelled_at=current,
            )


def _find(session: Session, code: str) -> Reservation | None:
    return session.scalar(select(Reservation).where(Reservation.code == code))


def _to_details(row: Reservation, reference: datetime) -> ReservationDetails:
    day = dr.parse_date(row.reservation_date)
    start = dr.parse_time(row.start_time)
    starts_at = dr.localize(day, start, reference)
    return ReservationDetails(
        code=row.code,
        customer_name=row.customer_name,
        customer_phone=row.customer_phone,
        customer_email=row.customer_email,
        party_size=row.party_size,
        date=day,
        start_time=start,
        end_time=dr.parse_time(row.end_time),
        status=ReservationStatus(row.status),
        zone=Zone(row.tables[0].zone) if row.tables else None,
        table_labels=tuple(t.label for t in row.tables),
        notes=row.notes,
        starts_at=starts_at,
        free_cancellation_until=starts_at - rules.FREE_CANCELLATION_NOTICE,
        late_tolerance_minutes=rules.LATE_TOLERANCE_MINUTES,
        cancelled_at=datetime.fromisoformat(row.cancelled_at) if row.cancelled_at else None,
        cancellation_reason=row.cancellation_reason,
    )
