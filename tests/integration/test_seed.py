"""Cada pré-condição do cabeçalho de evals/dataset.yaml, verificada no banco semeado."""

from collections.abc import Iterator
from datetime import date, time, timedelta

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from mesa_certa.config import Settings
from mesa_certa.db.models import (
    Base,
    Closure,
    DailySpecial,
    DiningTable,
    Reservation,
    ServiceHour,
)
from mesa_certa.db.reset import reset_database
from mesa_certa.db.session import create_db_engine, create_session_factory
from mesa_certa.domain.availability import AvailabilityService
from mesa_certa.domain.date_resolver import FixedClock
from mesa_certa.domain.menu import MenuService
from mesa_certa.domain.rules import Zone
from tests.integration.conftest import MIGRATIONS_PATH, at


@pytest.fixture
def migrated_engine(settings: Settings) -> Iterator[Engine]:
    reset_database(settings.database_url, MIGRATIONS_PATH)
    engine = create_db_engine(settings.database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def factory(migrated_engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(migrated_engine)


def dump(engine: Engine) -> list[str]:
    """Dump SQL bruto, sensível à ordem física das linhas."""
    raw = engine.raw_connection()
    try:
        return list(raw.driver_connection.iterdump())  # type: ignore[union-attr]
    finally:
        raw.close()


def test_migracao_bate_com_os_modelos(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []


def test_seed_e_deterministico(settings: Settings, migrated_engine: Engine) -> None:
    first = dump(migrated_engine)
    migrated_engine.dispose()

    reset_database(settings.database_url, MIGRATIONS_PATH)

    assert dump(migrated_engine) == first


def test_salao_e_horarios(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        tables = session.scalars(select(DiningTable)).all()
        hours = session.scalars(select(ServiceHour)).all()

    reservable = [t for t in tables if t.reservable]
    assert len(reservable) == 16
    assert sum(t.capacity for t in reservable) == 64
    assert [t.label for t in tables if not t.reservable] == ["B1"]
    assert all(t.combinable == (t.zone == Zone.MEZANINO) for t in reservable)
    assert len(hours) == 8  # ter a qui jantar, sex e sáb almoço e jantar, dom almoço
    assert 0 not in {h.weekday for h in hours}


def test_doze_reservas(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        assert session.scalar(select(func.count(Reservation.id))) == 12


def test_mezanino_lotado_no_sabado_19(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        rows = session.scalars(
            select(Reservation).where(
                Reservation.reservation_date == "2026-09-19",
                Reservation.status == "CONFIRMADA",
            )
        ).all()
        mezanino = {t.label: r for r in rows for t in r.tables if t.zone == Zone.MEZANINO.value}
        other_zones = [t for r in rows for t in r.tables if t.zone != Zone.MEZANINO.value]

    assert sorted(mezanino) == ["M1", "M2", "M3", "M4"]
    for reservation in mezanino.values():
        assert (reservation.party_size, reservation.start_time, reservation.end_time) == (
            6,
            "19:30",
            "21:30",
        )
    assert other_zones == []


def test_k7m2qp_e_w4x9ht(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        k7 = session.scalars(select(Reservation).where(Reservation.code == "K7M2QP")).one()
        w4 = session.scalars(select(Reservation).where(Reservation.code == "W4X9HT")).one()

        assert k7.status == "CONFIRMADA"
        assert k7.customer_name == "Bruna Alves"
        assert k7.party_size == 2
        assert (k7.reservation_date, k7.start_time) == ("2026-09-26", "20:00")
        assert [t.zone for t in k7.tables] == [Zone.VARANDA.value]
        assert w4.status == "CANCELADA"


def test_horarios_livres_exigidos(factory: sessionmaker[Session]) -> None:
    clock = FixedClock(at(2026, 9, 15, 14))
    service = AvailabilityService(factory, clock)

    sat_19_couple = service.check(date(2026, 9, 19), 2, time(20, 0))
    assert sat_19_couple.requested.available
    sat_19_salao = service.check(date(2026, 9, 19), 4, time(20, 0))
    assert sat_19_salao.requested.zone is Zone.SALAO

    full = service.check(date(2026, 9, 19), 6, time(20, 0))
    assert not full.requested.available
    assert [s.time for s in full.alternatives] == [time(21, 30), time(22, 0), time(22, 30)]

    assert service.check(date(2026, 9, 18), 2, time(19, 0)).requested.available
    wed = service.check(date(2026, 9, 16), 3)
    assert wed.alternatives[0].time == time(18, 0)

    clock.instant = at(2026, 9, 22, 14)
    sat_26 = service.check(date(2026, 9, 26), 6, time(20, 0))
    assert sat_26.requested.available
    assert sat_26.requested.zone is Zone.MEZANINO


def test_pratos_do_dia(factory: sessionmaker[Session]) -> None:
    menu = MenuService(factory)

    for offset in range(14):
        day = date(2026, 9, 15) + timedelta(days=offset)
        specials = menu.list_for(day)
        assert len(specials) == 2
        assert all(s.price_brl > 0 for s in specials)

    assert menu.list_for(date(2026, 11, 10)) == []
    with factory() as session:
        assert session.scalar(select(func.max(DailySpecial.special_date))) == "2026-09-28"


def test_tres_fechamentos_fora_dos_casos(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        closures = [c.closure_date for c in session.scalars(select(Closure))]

    assert len(closures) == 3
    assert {"2026-12-25", "2027-01-01"} <= set(closures)
    assert not any("2026-09-15" <= c <= "2026-09-28" or c == "2026-11-10" for c in closures)
