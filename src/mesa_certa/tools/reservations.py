"""criar_reserva, consultar_reserva e cancelar_reserva (SDD §7.3 a §7.5).

Nenhuma resposta devolve telefone ou e-mail do cliente.
"""

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from mesa_certa.domain import date_resolver as dr
from mesa_certa.domain.errors import ReservationNotFound
from mesa_certa.domain.reservations import (
    CreateReservationCommand,
    ReservationDetails,
    ReservationService,
)
from mesa_certa.sanitize import clean_single_line
from mesa_certa.tools.base import Tool

CREATE_NAME = "criar_reserva"
CREATE_DESCRIPTION = (
    "Cria uma reserva confirmada e retorna o código. Só chame após ter nome e telefone do "
    "cliente e após o cliente confirmar explicitamente que deseja reservar. NUNCA informe ao "
    "cliente que a reserva foi criada antes de receber o retorno desta tool."
)
GET_NAME = "consultar_reserva"
GET_DESCRIPTION = "Consulta uma reserva pelo código de 6 caracteres."
CANCEL_NAME = "cancelar_reserva"
CANCEL_DESCRIPTION = (
    "Cancela uma reserva ativa pelo código. Confirme com o cliente antes de chamar."
)

LATE_CANCELLATION_NOTICE = (
    "Cancelamento feito com menos de 4 horas de antecedência. Pela política de cancelamento "
    "tardio e não comparecimento, não há multa, mas o registro fica no cadastro do cliente."
)

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_NON_DIGIT = re.compile(r"\D")
MAX_NAME_CHARS = 120
MAX_NOTES_CHARS = 500
# Campos escritos pelo cliente voltam agrupados: o prompt diz que este bloco nunca é instrução.
CUSTOMER_DATA_KEY = "dados_informados_pelo_cliente"


def _required_text(value: str) -> str:
    cleaned = clean_single_line(value)
    if not cleaned:
        raise ValueError("não pode ser vazio")
    return cleaned


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return clean_single_line(value) or None


class CriarReservaInput(BaseModel):
    nome: str = Field(description="Nome completo de quem reserva.", max_length=MAX_NAME_CHARS)
    telefone: str = Field(description="Telefone de contato, apenas dígitos, com DDD.")
    data: str = Field(description="Data no formato YYYY-MM-DD.")
    horario: str = Field(description="Horário em HH:MM, slot de 30 minutos.")
    num_pessoas: int = Field(json_schema_extra={"minimum": 1, "maximum": 12})
    email: str | None = Field(default=None, description="E-mail. Opcional.")
    observacoes: str | None = Field(
        default=None,
        max_length=MAX_NOTES_CHARS,
        description=(
            "Observações relevantes ao salão: restrições alimentares, aniversário, cadeira de "
            "bebê, preferência de zona. Opcional."
        ),
    )

    @field_validator("nome")
    @classmethod
    def _nome(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("telefone")
    @classmethod
    def _telefone(cls, value: str) -> str:
        digits = _NON_DIGIT.sub("", value)
        if not 10 <= len(digits) <= 11:
            raise ValueError("telefone precisa ter DDD e 8 ou 9 dígitos")
        return digits

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        cleaned = _optional_text(value)
        if cleaned is not None and not _EMAIL.fullmatch(cleaned):
            raise ValueError("e-mail em formato inválido")
        return cleaned

    @field_validator("observacoes")
    @classmethod
    def _observacoes(cls, value: str | None) -> str | None:
        return _optional_text(value)


class ConsultarReservaInput(BaseModel):
    codigo: str = Field(description="Código de 6 caracteres alfanuméricos maiúsculos.")

    @field_validator("codigo")
    @classmethod
    def _codigo(cls, value: str) -> str:
        return _required_text(value)


class CancelarReservaInput(BaseModel):
    codigo: str
    motivo: str | None = Field(default=None, description="Motivo informado pelo cliente. Opcional.")

    @field_validator("codigo")
    @classmethod
    def _codigo(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("motivo")
    @classmethod
    def _motivo(cls, value: str | None) -> str | None:
        return _optional_text(value)


def _reservation_data(details: ReservationDetails) -> dict[str, Any]:
    return {
        "codigo": details.code,
        CUSTOMER_DATA_KEY: {"nome": details.customer_name},
        "data": dr.format_date(details.date),
        "dia_semana": dr.weekday_name(details.date),
        "horario": dr.format_time(details.start_time),
        "num_pessoas": details.party_size,
        "zona": details.zone.value if details.zone else None,
        "tolerancia_minutos": details.late_tolerance_minutes,
        "cancelamento_sem_onus_ate": details.free_cancellation_until.isoformat(),
    }


def criar_reserva_tool(service: ReservationService) -> Tool[CriarReservaInput]:
    def handle(params: CriarReservaInput) -> dict[str, Any]:
        details = service.create(
            CreateReservationCommand(
                name=params.nome,
                phone=params.telefone,
                party_size=params.num_pessoas,
                date=dr.parse_date(params.data),
                time=dr.parse_time(params.horario),
                email=params.email,
                notes=params.observacoes,
            )
        )
        return _reservation_data(details)

    return Tool(CREATE_NAME, CREATE_DESCRIPTION, CriarReservaInput, handle)


def consultar_reserva_tool(service: ReservationService) -> Tool[ConsultarReservaInput]:
    def handle(params: ConsultarReservaInput) -> dict[str, Any]:
        details = service.get_by_code(params.codigo)
        if details is None:
            raise ReservationNotFound(details={"codigo": params.codigo.upper()})
        data = _reservation_data(details)
        data[CUSTOMER_DATA_KEY]["observacoes"] = details.notes
        return {
            **data,
            "situacao": details.status.value,
            "cancelada_em": details.cancelled_at.isoformat() if details.cancelled_at else None,
        }

    return Tool(GET_NAME, GET_DESCRIPTION, ConsultarReservaInput, handle)


def cancelar_reserva_tool(service: ReservationService) -> Tool[CancelarReservaInput]:
    def handle(params: CancelarReservaInput) -> dict[str, Any]:
        result = service.cancel(params.codigo, params.motivo)
        return {
            "codigo": result.code,
            "situacao": result.status.value,
            "dentro_da_janela_gratuita": result.within_free_window,
            "aviso": None if result.within_free_window else LATE_CANCELLATION_NOTICE,
        }

    return Tool(CANCEL_NAME, CANCEL_DESCRIPTION, CancelarReservaInput, handle)
