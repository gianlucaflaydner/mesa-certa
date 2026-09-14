"""Pratos do dia (RF-06)."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from mesa_certa.db.models import DailySpecial
from mesa_certa.domain import date_resolver as dr


@dataclass(frozen=True)
class DailySpecialInfo:
    date: date
    dish_name: str
    description: str
    price_brl: float


class MenuService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_for(self, day: date) -> list[DailySpecialInfo]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(DailySpecial)
                .where(DailySpecial.special_date == dr.format_date(day))
                .order_by(DailySpecial.id)
            )
            return [DailySpecialInfo(day, r.dish_name, r.description, r.price_brl) for r in rows]
