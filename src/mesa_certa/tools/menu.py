"""listar_pratos_do_dia (SDD §7.6)."""

from typing import Any

from pydantic import BaseModel, Field

from mesa_certa.domain import date_resolver as dr
from mesa_certa.domain.menu import MenuService
from mesa_certa.tools.base import Tool

NAME = "listar_pratos_do_dia"
DESCRIPTION = (
    "Lista os pratos do dia de uma data específica. Use esta tool, e não a base de "
    "conhecimento, para prato do dia, pois é informação que muda diariamente."
)


class ListarPratosDoDiaInput(BaseModel):
    data: str | None = Field(
        default=None, description="Data no formato YYYY-MM-DD. Se omitida, usa hoje."
    )


def format_brl(value: float) -> str:
    return "R$ " + f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def listar_pratos_do_dia_tool(
    service: MenuService, clock: dr.Clock
) -> Tool[ListarPratosDoDiaInput]:
    def handle(params: ListarPratosDoDiaInput) -> dict[str, Any]:
        day = dr.parse_date(params.data) if params.data else clock.now().date()
        specials = service.list_for(day)
        return {
            "data": dr.format_date(day),
            "dia_semana": dr.weekday_name(day),
            "encontrou_pratos": bool(specials),
            "pratos": [
                {
                    "nome": s.dish_name,
                    "descricao": s.description,
                    "preco_brl": s.price_brl,
                    "preco_formatado": format_brl(s.price_brl),
                }
                for s in specials
            ],
        }

    return Tool(NAME, DESCRIPTION, ListarPratosDoDiaInput, handle)
