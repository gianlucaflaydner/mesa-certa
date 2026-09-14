"""Erros de domínio com código estável, consumido pelo agente (SDD §5.8)."""

from collections.abc import Mapping
from typing import ClassVar


class DomainError(Exception):
    def __init__(
        self, code: str, message: str, details: Mapping[str, object] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details: dict[str, object] = dict(details or {})


class _CodedError(DomainError):
    CODE: ClassVar[str]
    DEFAULT_MESSAGE: ClassVar[str]

    def __init__(
        self, message: str | None = None, details: Mapping[str, object] | None = None
    ) -> None:
        super().__init__(self.CODE, message or self.DEFAULT_MESSAGE, details)


class GroupTooLarge(_CodedError):
    CODE = "GRUPO_ACIMA_DO_LIMITE"
    DEFAULT_MESSAGE = "Grupos acima de 12 pessoas são tratados como evento privado."


class InvalidGroupSize(_CodedError):
    CODE = "GRUPO_INVALIDO"
    DEFAULT_MESSAGE = "O grupo precisa ter pelo menos 1 pessoa."


class OutsideBookingWindow(_CodedError):
    CODE = "FORA_DA_JANELA"
    DEFAULT_MESSAGE = "Reservas exigem entre 60 minutos e 60 dias de antecedência."


class DayClosed(_CodedError):
    CODE = "DIA_FECHADO"
    DEFAULT_MESSAGE = "O restaurante não abre nesta data."


class OutsideServiceHours(_CodedError):
    CODE = "HORARIO_FORA_DE_SERVICO"
    DEFAULT_MESSAGE = "O horário está fora do serviço ou após a última reserva."


class NoAvailability(_CodedError):
    CODE = "SEM_DISPONIBILIDADE"
    DEFAULT_MESSAGE = "Nenhuma mesa comporta o grupo neste horário."


class ReservationNotFound(_CodedError):
    CODE = "RESERVA_NAO_ENCONTRADA"
    DEFAULT_MESSAGE = "Nenhuma reserva encontrada com este código."


class AlreadyCancelled(_CodedError):
    CODE = "JA_CANCELADA"
    DEFAULT_MESSAGE = "A reserva não está ativa e não pode ser cancelada."


class InvalidDateFormat(_CodedError):
    CODE = "FORMATO_DATA_INVALIDO"
    DEFAULT_MESSAGE = "Data deve estar no formato YYYY-MM-DD."


class InvalidTimeFormat(_CodedError):
    CODE = "FORMATO_HORARIO_INVALIDO"
    DEFAULT_MESSAGE = "Horário deve estar no formato HH:MM, em slots de 30 minutos."
