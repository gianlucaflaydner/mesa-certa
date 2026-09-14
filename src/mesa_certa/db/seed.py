"""Carga determinística do banco (SDD §5.2).

Datas partem da âncora fixa, nunca do relógio. As pré-condições exigidas pelos casos de
avaliação estão no cabeçalho de `evals/dataset.yaml`, que é a fonte de verdade.
"""

import random
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from mesa_certa.db.models import (
    Closure,
    DailySpecial,
    DiningTable,
    Reservation,
    ServiceHour,
    reservation_tables,
)
from mesa_certa.domain import codes, rules
from mesa_certa.domain import date_resolver as dr
from mesa_certa.domain.availability import Booking, find_tables
from mesa_certa.domain.rules import ReservationStatus, Service, TableInfo, Zone

ANCHOR = date(2026, 9, 15)  # terça-feira
RANDOM_SEED = 42
SPECIALS_DAYS = 14
SPECIALS_PER_DAY = 2
TIMESTAMP_OFFSET = "-03:00"

_TABLES: list[tuple[str, Zone, int, bool, bool]] = [
    *((f"S{i}", Zone.SALAO, 4, False, True) for i in range(1, 9)),
    *((f"V{i}", Zone.VARANDA, 2, False, True) for i in range(1, 5)),
    *((f"M{i}", Zone.MEZANINO, 6, True, True) for i in range(1, 5)),
    ("B1", Zone.BALCAO, 8, False, False),
]

# Segunda (0) não abre.
_SERVICE_HOURS: list[tuple[int, Service, str, str]] = [
    *((weekday, Service.JANTAR, "18:00", "23:00") for weekday in (1, 2, 3)),
    *(
        (weekday, service, opens, closes)
        for weekday in (4, 5)
        for service, opens, closes in (
            (Service.ALMOCO, "12:00", "15:00"),
            (Service.JANTAR, "18:00", "00:00"),
        )
    ),
    (6, Service.ALMOCO, "12:00", "16:00"),
]

_CLOSURES: list[tuple[date, str]] = [
    (date(2026, 10, 14), "Manutenção da cozinha"),
    (date(2026, 12, 25), "Natal"),
    (date(2027, 1, 1), "Confraternização universal"),
]

_SPECIALS_POOL: list[tuple[str, str, float]] = [
    ("Arroz de pato no tucupi", "Pato confitado, arroz cremoso de tucupi e jambu.", 89.0),
    ("Galinhada caipira", "Galinha caipira, açafrão da terra e pequi.", 72.0),
    ("Peixe na folha de bananeira", "Peixe do dia assado na brasa com farofa de coco.", 94.0),
    ("Barreado de fogo lento", "Carne cozida por 12 horas, farinha e banana-da-terra.", 86.0),
    ("Nhoque de mandioquinha", "Manteiga de sálvia e queijo serrano.", 68.0),
    ("Polvo na brasa", "Batata-doce tostada e vinagrete de maxixe.", 118.0),
    ("Cuscuz de camarão", "Cuscuz paulista com camarão rosa e ovo cozido.", 92.0),
    ("Picadinho de fraldinha", "Arroz, ovo perfeito e farofa de banana.", 76.0),
]

_FIRST_NAMES = ["Ana", "Carlos", "Daniela", "Eduardo", "Fernanda", "Gustavo", "Juliana", "Marcos"]
_LAST_NAMES = ["Rocha", "Moreira", "Teixeira", "Cardoso", "Pereira", "Nunes", "Barros", "Freitas"]


@dataclass(frozen=True)
class _SeedReservation:
    day_offset: int
    start: str
    party_size: int
    status: ReservationStatus = ReservationStatus.CONFIRMADA
    code: str | None = None
    name: str | None = None
    phone: str | None = None
    notes: str | None = None
    cancellation_reason: str | None = None


_RESERVATIONS: list[_SeedReservation] = [
    # Sábado 2026-09-19: mezanino lotado das 19:30 às 21:30 (tool-004, tool-005).
    *(_SeedReservation(4, "19:30", 6) for _ in range(4)),
    # Sábado 2026-09-26, varanda (tool-009, tool-010).
    _SeedReservation(11, "20:00", 2, code="K7M2QP", name="Bruna Alves", phone="51988887777"),
    _SeedReservation(
        10,
        "20:00",
        4,
        status=ReservationStatus.CANCELADA,
        code="W4X9HT",
        cancellation_reason="Mudança de planos",
    ),
    # Demais reservas, longe dos horários livres exigidos pelo dataset.
    _SeedReservation(2, "20:00", 4, notes="Aniversário"),
    _SeedReservation(3, "12:00", 2),
    _SeedReservation(5, "12:30", 5, notes="Cadeira de bebê"),
    _SeedReservation(7, "19:30", 3),
    _SeedReservation(9, "21:00", 8),
    _SeedReservation(12, "13:00", 2),
]


def _timestamp(day: date, at: str) -> str:
    return f"{day.isoformat()}T{at}:00{TIMESTAMP_OFFSET}"


def seed(session: Session) -> None:
    """Popula um banco vazio. Mesmo resultado a cada execução."""
    rng = random.Random(RANDOM_SEED)

    tables = [
        DiningTable(label=label, zone=zone.value, capacity=cap, combinable=comb, reservable=res)
        for label, zone, cap, comb, res in _TABLES
    ]
    session.add_all(tables)
    session.add_all(
        ServiceHour(weekday=wd, service=service.value, opens_at=opens, closes_at=closes)
        for wd, service, opens, closes in _SERVICE_HOURS
    )
    session.add_all(Closure(closure_date=d.isoformat(), reason=r) for d, r in _CLOSURES)
    session.flush()

    # Todos os dias de 15 a 28, inclusive segundas, como pede o dataset.
    for offset in range(SPECIALS_DAYS):
        day = ANCHOR + timedelta(days=offset)
        for name, description, price in rng.sample(_SPECIALS_POOL, SPECIALS_PER_DAY):
            session.add(
                DailySpecial(
                    special_date=day.isoformat(),
                    dish_name=name,
                    description=description,
                    price_brl=price,
                )
            )

    _seed_reservations(session, tables, rng)


def _seed_reservations(session: Session, tables: list[DiningTable], rng: random.Random) -> None:
    infos = [
        TableInfo(t.id, t.label, Zone(t.zone), t.capacity, t.combinable)
        for t in tables
        if t.reservable
    ]
    links: list[dict[str, int]] = []
    bookings: dict[date, list[Booking]] = {}
    used_codes = {spec.code for spec in _RESERVATIONS if spec.code}
    created = ANCHOR - timedelta(days=5)

    for index, spec in enumerate(_RESERVATIONS):
        day = ANCHOR + timedelta(days=spec.day_offset)
        start = dr.parse_time(spec.start)
        start_min = dr.minutes_since_midnight(start)
        allocation = find_tables(infos, bookings.get(day, []), start_min, spec.party_size)
        if allocation is None:
            raise RuntimeError(f"Seed inconsistente: sem mesa para {spec}")

        end_min = start_min + rules.stay_minutes(spec.party_size)
        if spec.status is ReservationStatus.CONFIRMADA:
            bookings.setdefault(day, []).append(
                Booking(start_min, end_min, frozenset(t.id for t in allocation))
            )

        code = spec.code or codes.generate_unique_code(lambda c: c in used_codes, rng)
        used_codes.add(code)
        name = spec.name or f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"
        phone = spec.phone or f"519{rng.randrange(10**7, 10**8)}"
        stamp = _timestamp(created, f"{9 + index:02d}:00")

        row = Reservation(
            code=code,
            customer_name=name,
            customer_phone=phone,
            customer_email=None,
            party_size=spec.party_size,
            reservation_date=day.isoformat(),
            start_time=spec.start,
            end_time=dr.format_time(dr.time_from_minutes(end_min)),
            status=spec.status.value,
            notes=spec.notes,
            cancelled_at=(
                _timestamp(ANCHOR - timedelta(days=1), "18:00")
                if spec.status is ReservationStatus.CANCELADA
                else None
            ),
            cancellation_reason=spec.cancellation_reason,
            created_at=stamp,
            updated_at=stamp,
        )
        session.add(row)
        session.flush()
        links.extend({"reservation_id": row.id, "table_id": t.id} for t in allocation)

    # Inserção explícita: o relacionamento grava a associação em ordem de conjunto, o que
    # mudaria a ordem física das linhas entre execuções.
    session.execute(insert(reservation_tables), links)
    session.expire_all()


def is_empty(session: Session) -> bool:
    return session.scalar(select(DiningTable.id).limit(1)) is None
