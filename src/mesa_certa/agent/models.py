"""Estruturas de resultado de um turno (SDD §8.3)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

ReservationKind = Literal["criada", "consultada", "cancelada"]


@dataclass(frozen=True)
class ReservationEvent:
    """Reserva tocada no turno, com os dados exatos que a tool devolveu (nunca do texto)."""

    kind: ReservationKind
    data: Mapping[str, Any]


@dataclass(frozen=True)
class Attachment:
    """Arquivo entregue ao cliente no turno, com os dados exatos que a tool devolveu."""

    kind: str
    title: str
    filename: str
    url: str
    size_kb: int


@dataclass(frozen=True)
class Citation:
    source: str
    section: str
    chunk_id: str


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    ok: bool
    duration_ms: int
    error_code: str | None = None


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def add(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read_input_tokens: int | None = None,
        cache_creation_input_tokens: int | None = None,
    ) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cache_read_input_tokens += cache_read_input_tokens or 0
        self.cache_creation_input_tokens += cache_creation_input_tokens or 0


@dataclass
class TurnResult:
    session_id: str
    trace_id: str
    reply: str
    citations: list[Citation] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    iterations: int = 0
    exhausted: bool = False
    guard_violations: list[str] = field(default_factory=list)
    reservation: ReservationEvent | None = None
    attachments: list[Attachment] = field(default_factory=list)
    latency_ms: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)
