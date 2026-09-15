"""Loop de tool calling próprio (SDD §8.1, ADR-001).

Cada iteração chama o modelo com o histórico da sessão. Se ele pedir tools, todas as tools
da resposta são executadas e os resultados voltam num único bloco de usuário. O turno
termina quando o modelo responde sem pedir tool, ou quando o limite de iterações estoura.
"""

import time
from typing import Any

from anthropic.types import Message

from mesa_certa.agent.guards import ToolOutcome, check_reply
from mesa_certa.agent.llm import LLMClient
from mesa_certa.agent.models import (
    Attachment,
    Citation,
    ReservationEvent,
    ReservationKind,
    ToolCallRecord,
    TurnResult,
)
from mesa_certa.agent.prompts import build_system_prompt
from mesa_certa.agent.session import Session
from mesa_certa.domain.date_resolver import Clock
from mesa_certa.domain.rules import RESTAURANT_PHONE
from mesa_certa.observability.tracing import KNOWLEDGE_TOOL, Trace, Tracer
from mesa_certa.sanitize import MAX_MESSAGE_CHARS, clean_message
from mesa_certa.tools.base import ToolResult
from mesa_certa.tools.documents import NAME as DOCUMENT_TOOL
from mesa_certa.tools.registry import ToolRegistry

TRACE_ID_ATTR = "trace_id"

EXHAUSTED_REPLY = (
    "Desculpe, não consegui concluir o seu pedido agora. Para não passar nenhuma informação "
    f"errada, fale com a equipe pelo telefone {RESTAURANT_PHONE}."
)
REFUSAL_REPLY = (
    "Não consigo ajudar com esse pedido. Posso tirar dúvidas sobre o Mesa Certa ou cuidar "
    "da sua reserva."
)
EMPTY_REPLY = (
    f"Desculpe, não consegui formular uma resposta. Tente de novo ou ligue {RESTAURANT_PHONE}."
)


class AgentLoop:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        clock: Clock,
        tracer: Tracer,
        max_iterations: int = 8,
        max_message_chars: int = MAX_MESSAGE_CHARS,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._clock = clock
        self._tracer = tracer
        self.max_iterations = max_iterations
        self.max_message_chars = max_message_chars

    def run_turn(self, session: Session, user_message: str) -> TurnResult:
        """Executa um turno. Levanta `MessageTooLong` antes de tocar sessão ou modelo."""
        user_message = clean_message(user_message, self.max_message_chars)
        started = time.perf_counter()
        trace = self._tracer.start_turn(session.id, user_message)
        turn = TurnResult(session_id=session.id, trace_id=trace.trace_id, reply="")
        outcomes: list[ToolOutcome] = []
        session.append_user(user_message)

        try:
            for iteration in range(1, self.max_iterations + 1):
                response = self._call_model(session, trace, iteration, turn)
                turn.iterations = iteration
                tool_uses = [b for b in response.content if b.type == "tool_use"]

                if response.stop_reason != "tool_use" or not tool_uses:
                    # tool_use sem tool_result (resposta truncada) invalidaria o próximo turno.
                    session.append_assistant(
                        b.to_dict(mode="json") for b in response.content if b.type != "tool_use"
                    )
                    turn.reply = _final_reply(response)
                    self._guard_reply(session, turn, trace, outcomes)
                    turn.reservation = _reservation_event(outcomes)
                    turn.attachments = _attachments(outcomes)
                    return self._finish(turn, trace, started)

                session.append_assistant(b.to_dict(mode="json") for b in response.content)

                results = [
                    self._run_tool(b.id, b.name, b.input, trace, turn, outcomes) for b in tool_uses
                ]
                session.append_tool_results(results)
        except Exception as exc:
            self._tracer.finish(trace, "", error=type(exc).__name__)
            # A API devolve o trace_id no erro 500 para a falha poder ser investigada.
            setattr(exc, TRACE_ID_ATTR, trace.trace_id)
            raise

        turn.exhausted = trace.exhausted = True
        turn.reply = EXHAUSTED_REPLY
        session.append_assistant([{"type": "text", "text": EXHAUSTED_REPLY}])
        return self._finish(turn, trace, started)

    def _call_model(
        self, session: Session, trace: Trace, iteration: int, turn: TurnResult
    ) -> Message:
        t0 = time.perf_counter()
        response = self._llm.create(
            system=build_system_prompt(self._clock.now()),
            tools=self._registry.schemas(),
            messages=session.to_api_messages(),
        )
        usage = response.usage
        turn.usage.add(
            usage.input_tokens,
            usage.output_tokens,
            usage.cache_read_input_tokens,
            usage.cache_creation_input_tokens,
        )
        trace.record_llm_call(
            iteration=iteration,
            stop_reason=response.stop_reason,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_input_tokens=usage.cache_read_input_tokens or 0,
            duration_ms=_ms_since(t0),
        )
        return response

    def _run_tool(
        self,
        tool_use_id: str,
        name: str,
        args: object,
        trace: Trace,
        turn: TurnResult,
        outcomes: list[ToolOutcome],
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        result = self._registry.dispatch(name, args)
        duration_ms = _ms_since(t0)
        trace.record_tool_call(name, args, result, duration_ms)
        outcomes.append(
            ToolOutcome(name, result.ok, result.data, result.error.code if result.error else None)
        )
        turn.tool_calls.append(
            ToolCallRecord(
                name=name,
                ok=result.ok,
                duration_ms=duration_ms,
                error_code=result.error.code if result.error else None,
            )
        )
        if name == KNOWLEDGE_TOOL:
            _collect_citations(result, turn.citations)
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": result.to_json(),
            "is_error": not result.ok,
        }

    def _guard_reply(
        self, session: Session, turn: TurnResult, trace: Trace, outcomes: list[ToolOutcome]
    ) -> None:
        guard = check_reply(turn.reply, outcomes, session.customer_and_tool_text())
        if not guard.replaced:
            return
        turn.reply = guard.reply
        turn.guard_violations = trace.guard_violations = guard.violations
        session.replace_last_reply(guard.reply)

    def _finish(self, turn: TurnResult, trace: Trace, started: float) -> TurnResult:
        turn.latency_ms = _ms_since(started)
        self._tracer.finish(trace, turn.reply)
        return turn


def _final_reply(response: Message) -> str:
    if response.stop_reason == "refusal":
        return REFUSAL_REPLY
    text = "\n\n".join(b.text for b in response.content if b.type == "text").strip()
    return text or EMPTY_REPLY


_RESERVATION_TOOLS: dict[str, ReservationKind] = {
    "criar_reserva": "criada",
    "cancelar_reserva": "cancelada",
    "consultar_reserva": "consultada",
}


def _reservation_event(outcomes: list[ToolOutcome]) -> ReservationEvent | None:
    """A última reserva criada, cancelada ou consultada com sucesso no turno."""
    for outcome in reversed(outcomes):
        kind = _RESERVATION_TOOLS.get(outcome.name)
        if kind is not None and outcome.ok and outcome.data is not None:
            return ReservationEvent(kind, dict(outcome.data))
    return None


def _attachments(outcomes: list[ToolOutcome]) -> list[Attachment]:
    """Arquivos entregues com sucesso no turno, um por tipo."""
    found: dict[str, Attachment] = {}
    for outcome in outcomes:
        data = outcome.data
        if outcome.name != DOCUMENT_TOOL or not outcome.ok or data is None:
            continue
        found[str(data["tipo"])] = Attachment(
            kind=str(data["tipo"]),
            title=str(data["titulo"]),
            filename=str(data["arquivo"]),
            url=str(data["url"]),
            size_kb=int(data["tamanho_kb"]),
        )
    return list(found.values())


def _collect_citations(result: ToolResult, citations: list[Citation]) -> None:
    if not result.ok or result.data is None:
        return
    seen = {c.chunk_id for c in citations}
    for chunk in result.data.get("trechos") or []:
        chunk_id = str(chunk.get("chunk_id", ""))
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        citations.append(
            Citation(
                source=str(chunk.get("fonte", "")),
                section=str(chunk.get("secao", "")),
                chunk_id=chunk_id,
            )
        )


def _ms_since(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)
