"""consultar_disponibilidade (SDD §7.2).

`num_pessoas` declara 1 a 20 no schema, mas não valida aqui: quem recusa é o domínio,
com `GRUPO_INVALIDO` ou `GRUPO_ACIMA_DO_LIMITE`, que são mais úteis ao modelo que um
erro genérico de argumento.
"""

from typing import Any

from pydantic import BaseModel, Field

from mesa_certa.domain import date_resolver as dr
from mesa_certa.domain.availability import AvailabilityService
from mesa_certa.domain.errors import DayClosed
from mesa_certa.tools.base import Tool

NAME = "consultar_disponibilidade"
DESCRIPTION = (
    "Consulta disponibilidade real de mesas. Use SEMPRE antes de afirmar qualquer coisa sobre "
    "mesa livre ou horário. Nunca afirme disponibilidade sem chamar esta tool."
)
NO_AVAILABILITY = "SEM_DISPONIBILIDADE"


class ConsultarDisponibilidadeInput(BaseModel):
    data: str = Field(description="Data no formato YYYY-MM-DD.")
    num_pessoas: int = Field(
        description="Número de pessoas no grupo.",
        json_schema_extra={"minimum": 1, "maximum": 20},
    )
    horario: str | None = Field(
        default=None,
        description=(
            "Horário desejado em HH:MM, em slots de 30 minutos. Opcional. Se omitido, retorna "
            "todos os horários livres do dia."
        ),
    )


def consultar_disponibilidade_tool(
    service: AvailabilityService,
) -> Tool[ConsultarDisponibilidadeInput]:
    def handle(params: ConsultarDisponibilidadeInput) -> dict[str, Any]:
        day = dr.parse_date(params.data)
        at = dr.parse_time(params.horario) if params.horario is not None else None
        result = service.check(day, params.num_pessoas, at)

        if result.closed_reason is not None:
            raise DayClosed(
                details={
                    "data": dr.format_date(day),
                    "dia_semana": dr.weekday_name(day),
                    "motivo": result.closed_reason,
                    "proxima_data_aberta": (
                        dr.format_date(result.next_open_date) if result.next_open_date else None
                    ),
                }
            )

        alternatives = [
            {"horario": dr.format_time(slot.time), "zona": slot.zone.value}
            for slot in result.alternatives
            if slot.time is not None and slot.zone is not None
        ]
        available = result.requested.available if at is not None else bool(alternatives)
        return {
            "data": dr.format_date(day),
            "dia_semana": dr.weekday_name(day),
            "horario_solicitado": dr.format_time(at) if at is not None else None,
            "num_pessoas": params.num_pessoas,
            "disponivel": available,
            "zona": result.requested.zone.value if result.requested.zone else None,
            "motivo": None if available else NO_AVAILABILITY,
            "alternativas": alternatives,
        }

    return Tool(NAME, DESCRIPTION, ConsultarDisponibilidadeInput, handle)
