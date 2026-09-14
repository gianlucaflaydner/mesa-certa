"""Engine e sessões do SQLite.

O pysqlite abre transações por conta própria e não sabe fazer `BEGIN IMMEDIATE`. Por isso
o controle é desligado na conexão e o `BEGIN` é emitido no evento `begin` do SQLAlchemy.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, make_url
from sqlalchemy.orm import Session, sessionmaker

_BEGIN_OPTION = "sqlite_begin"
_BUSY_TIMEOUT_SECONDS = 15


def create_db_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return create_engine(url)

    if url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": _BUSY_TIMEOUT_SECONDS},
    )

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: Any, _record: Any) -> None:
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _on_begin(connection: Any) -> None:
        connection.exec_driver_sql(connection.get_execution_options().get(_BEGIN_OPTION, "BEGIN"))

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def write_transaction(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Transação com trava de escrita desde o início (`BEGIN IMMEDIATE`)."""
    with factory() as session, session.begin():
        session.connection(execution_options={_BEGIN_OPTION: "BEGIN IMMEDIATE"})
        yield session
