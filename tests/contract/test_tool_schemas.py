"""O schema enviado ao modelo é o mesmo JSON publicado no SDD §7."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import sessionmaker

from mesa_certa.domain.availability import AvailabilityService
from mesa_certa.domain.date_resolver import FixedClock
from mesa_certa.domain.menu import MenuService
from mesa_certa.domain.reservations import ReservationService
from mesa_certa.rag.retriever import Retriever
from mesa_certa.rag.store import ChunkStore
from mesa_certa.tools import ToolServices, build_registry
from mesa_certa.tools.registry import ToolRegistry
from tests.fakes import HashingEmbedder

SDD = Path(__file__).resolve().parents[2] / "docs" / "SDD.md"


def sdd_schemas() -> dict[str, dict[str, Any]]:
    blocks = re.findall(r"```json\n(.*?)```", SDD.read_text(encoding="utf-8"), re.DOTALL)
    tools = [json.loads(block) for block in blocks if '"input_schema"' in block]
    return {tool["name"]: tool for tool in tools}


EXPECTED = sdd_schemas()


@pytest.fixture(scope="module")
def registry(tmp_path_factory: pytest.TempPathFactory) -> ToolRegistry:
    clock = FixedClock(datetime(2026, 9, 15, 14))
    factory = sessionmaker()
    services = ToolServices(
        availability=AvailabilityService(factory, clock),
        reservations=ReservationService(factory, clock),
        menu=MenuService(factory),
        clock=clock,
    )
    store = ChunkStore(tmp_path_factory.mktemp("chroma"), "contrato")
    return build_registry(services, Retriever(HashingEmbedder(), store))


def test_sdd_publica_as_sete_tools() -> None:
    assert len(EXPECTED) == 7


def test_registry_expoe_exatamente_as_tools_do_sdd(registry: ToolRegistry) -> None:
    assert sorted(registry.names) == sorted(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_schema_bate_com_o_sdd(registry: ToolRegistry, name: str) -> None:
    [schema] = [s for s in registry.schemas() if s["name"] == name]

    assert schema == EXPECTED[name]
