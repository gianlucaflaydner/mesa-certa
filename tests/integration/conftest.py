from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from mesa_certa.config import Settings
from mesa_certa.db.models import Base
from mesa_certa.db.seed import seed
from mesa_certa.db.session import create_db_engine, create_session_factory
from mesa_certa.domain.availability import AvailabilityService
from mesa_certa.domain.date_resolver import FixedClock
from mesa_certa.domain.reservations import ReservationService

MIGRATIONS_PATH = Path(__file__).resolve().parents[2] / "migrations"
SP = ZoneInfo("America/Sao_Paulo")


def at(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=SP)


@pytest.fixture
def engine(settings: Settings) -> Iterator[Engine]:
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    factory = create_session_factory(engine)
    with factory.begin() as session:
        seed(session)
    return factory


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(at(2026, 9, 15, 14))


@pytest.fixture
def availability(session_factory: sessionmaker[Session], clock: FixedClock) -> AvailabilityService:
    return AvailabilityService(session_factory, clock)


@pytest.fixture
def reservations(session_factory: sessionmaker[Session], clock: FixedClock) -> ReservationService:
    return ReservationService(session_factory, clock)
