"""Tabelas do SDD §5.1.

Datas ficam como 'YYYY-MM-DD', horários como 'HH:MM' e instantes como ISO 8601 com fuso.
"""

from typing import Any, ClassVar

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from mesa_certa.domain.rules import (
    MAX_PARTY_SIZE,
    MIN_PARTY_SIZE,
    ReservationStatus,
    Service,
    Zone,
)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _in_list(column: str, values: list[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {str: Text()}


reservation_tables = Table(
    "reservation_tables",
    Base.metadata,
    Column(
        "reservation_id",
        ForeignKey("reservations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("table_id", ForeignKey("tables.id"), primary_key=True),
)


class DiningTable(Base):
    __tablename__ = "tables"
    __table_args__ = (CheckConstraint(_in_list("zone", [z.value for z in Zone]), name="zone"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(unique=True)
    zone: Mapped[str]
    capacity: Mapped[int]
    combinable: Mapped[bool] = mapped_column(default=False)
    reservable: Mapped[bool] = mapped_column(default=True)


class ServiceHour(Base):
    __tablename__ = "service_hours"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday"),
        CheckConstraint(_in_list("service", [s.value for s in Service]), name="service"),
        UniqueConstraint("weekday", "service"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    weekday: Mapped[int]
    service: Mapped[str]
    opens_at: Mapped[str]
    closes_at: Mapped[str]


class Closure(Base):
    __tablename__ = "closures"

    id: Mapped[int] = mapped_column(primary_key=True)
    closure_date: Mapped[str] = mapped_column(unique=True)
    reason: Mapped[str]


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint(
            f"party_size BETWEEN {MIN_PARTY_SIZE} AND {MAX_PARTY_SIZE}", name="party_size"
        ),
        CheckConstraint(_in_list("status", [s.value for s in ReservationStatus]), name="status"),
        Index("idx_reservations_date_status", "reservation_date", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    customer_name: Mapped[str]
    customer_phone: Mapped[str]
    customer_email: Mapped[str | None]
    party_size: Mapped[int]
    reservation_date: Mapped[str]
    start_time: Mapped[str]
    end_time: Mapped[str]
    status: Mapped[str]
    notes: Mapped[str | None]
    cancelled_at: Mapped[str | None]
    cancellation_reason: Mapped[str | None]
    created_at: Mapped[str]
    updated_at: Mapped[str]

    tables: Mapped[list[DiningTable]] = relationship(
        secondary=reservation_tables, order_by=DiningTable.id
    )


class DailySpecial(Base):
    __tablename__ = "daily_specials"
    __table_args__ = (
        UniqueConstraint("special_date", "dish_name"),
        Index("idx_specials_date", "special_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    special_date: Mapped[str]
    dish_name: Mapped[str]
    description: Mapped[str]
    price_brl: Mapped[float]
