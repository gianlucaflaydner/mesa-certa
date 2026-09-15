"""Tools expostas ao modelo e seu registry."""

from dataclasses import dataclass

from mesa_certa.domain.availability import AvailabilityService
from mesa_certa.domain.date_resolver import Clock
from mesa_certa.domain.menu import MenuService
from mesa_certa.domain.reservations import ReservationService
from mesa_certa.rag.retriever import Retriever
from mesa_certa.tools.availability import consultar_disponibilidade_tool
from mesa_certa.tools.knowledge import buscar_conhecimento_tool
from mesa_certa.tools.menu import listar_pratos_do_dia_tool
from mesa_certa.tools.registry import ToolCallObserver, ToolRegistry
from mesa_certa.tools.reservations import (
    cancelar_reserva_tool,
    consultar_reserva_tool,
    criar_reserva_tool,
)


@dataclass(frozen=True)
class ToolServices:
    availability: AvailabilityService
    reservations: ReservationService
    menu: MenuService
    clock: Clock


def build_registry(
    services: ToolServices, retriever: Retriever, observer: ToolCallObserver | None = None
) -> ToolRegistry:
    registry = ToolRegistry(observer)
    registry.register(buscar_conhecimento_tool(retriever))
    registry.register(consultar_disponibilidade_tool(services.availability))
    registry.register(criar_reserva_tool(services.reservations))
    registry.register(consultar_reserva_tool(services.reservations))
    registry.register(cancelar_reserva_tool(services.reservations))
    registry.register(listar_pratos_do_dia_tool(services.menu, services.clock))
    return registry
