"""Contratos HTTP da API (SDD §9.2 e §9.3)."""

from typing import Literal

from pydantic import BaseModel, Field

from mesa_certa.agent.models import TurnResult
from mesa_certa.sanitize import MAX_MESSAGE_CHARS


class ChatRequest(BaseModel):
    session_id: str | None = Field(
        default=None, description="Sessão existente. Ausente: uma nova sessão é criada."
    )
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class CitationOut(BaseModel):
    source: str
    section: str
    chunk_id: str


class ToolCallOut(BaseModel):
    name: str
    ok: bool
    duration_ms: int
    error_code: str | None = None


class ReservationOut(BaseModel):
    """Reserva do turno, com os campos que a tool devolveu. Nunca inclui telefone ou e-mail."""

    tipo: Literal["criada", "consultada", "cancelada"]
    codigo: str
    data: str | None = None
    dia_semana: str | None = None
    horario: str | None = None
    num_pessoas: int | None = None
    zona: str | None = None
    tolerancia_minutos: int | None = None
    cancelamento_sem_onus_ate: str | None = None
    situacao: str | None = None
    dentro_da_janela_gratuita: bool | None = None
    aviso: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    trace_id: str
    reply: str
    citations: list[CitationOut]
    tool_calls: list[ToolCallOut]
    latency_ms: int
    iterations: int
    exhausted: bool
    guard_violations: list[str]
    reservation: ReservationOut | None

    @classmethod
    def from_turn(cls, turn: TurnResult) -> "ChatResponse":
        event = turn.reservation
        fields = set(ReservationOut.model_fields) - {"tipo"}
        reservation = (
            ReservationOut(tipo=event.kind, **{k: v for k, v in event.data.items() if k in fields})
            if event is not None
            else None
        )
        return cls(
            reservation=reservation,
            session_id=turn.session_id,
            trace_id=turn.trace_id,
            reply=turn.reply,
            citations=[
                CitationOut(source=c.source, section=c.section, chunk_id=c.chunk_id)
                for c in turn.citations
            ],
            tool_calls=[
                ToolCallOut(
                    name=t.name, ok=t.ok, duration_ms=t.duration_ms, error_code=t.error_code
                )
                for t in turn.tool_calls
            ],
            latency_ms=turn.latency_ms,
            iterations=turn.iterations,
            exhausted=turn.exhausted,
            guard_violations=list(turn.guard_violations),
        )


class ErrorOut(BaseModel):
    error: str
    detail: str | None = None
    trace_id: str | None = None


class HealthOut(BaseModel):
    status: Literal["ok", "degradado"]
    checks: dict[str, bool]


class ReindexOut(BaseModel):
    criados: int
    atualizados: int
    removidos: int
    inalterados: int
