"""Recria o banco do zero: apaga, migra e semeia."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import make_url

from mesa_certa.db.seed import seed
from mesa_certa.db.session import create_db_engine, create_session_factory

_SQLITE_SIDE_FILES = ("", "-journal", "-wal", "-shm")


def alembic_config(database_url: str, migrations_path: Path) -> Config:
    config = Config()
    config.set_main_option("script_location", str(migrations_path))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade(database_url: str, migrations_path: Path) -> None:
    command.upgrade(alembic_config(database_url, migrations_path), "head")


def reset_database(database_url: str, migrations_path: Path) -> None:
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
        for suffix in _SQLITE_SIDE_FILES:
            Path(url.database + suffix).unlink(missing_ok=True)

    upgrade(database_url, migrations_path)

    engine = create_db_engine(database_url)
    try:
        with create_session_factory(engine).begin() as session:
            seed(session)
    finally:
        engine.dispose()
