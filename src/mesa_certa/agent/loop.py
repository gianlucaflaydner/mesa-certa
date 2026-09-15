"""Loop de tool calling próprio (SDD §8.1, ADR-001).

Cada iteração chama o modelo com o histórico da sessão. Se ele pedir tools, todas as tools
da resposta são executadas e os resultados voltam num único bloco de usuário. O turno
termina quando o modelo responde sem pedir tool, ou quando o limite de iterações estoura.
"""

import time
from typing import Any

from anthropic.types import Message

from mesa_certa.agent.llm import LLMClient
from mesa_certa.agent.models import Citation, ToolCallRecord, TurnResult
from mesa_certa.agent.prompts import build_system_prompt
from mesa_certa.agent.session import Session
from mesa_certa.domain.date_resolver import Clock
from mesa_certa.domain.rules import RESTAURANT_PHONE
from mesa_certa.observability.tracing import KNOWLEDGE_TOOL, Trace, Tracer
from mesa_certa.tools.base import ToolResult
from mesa_certa.tools.registry import ToolRegistry

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
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._clock = clock
        self._tracer = tracer
        self.max_iterations = max_iterations

    def run_turn(self, session: Session, user_message: str) -> TurnResult:
        started = time.perf_counter()
        trace = self._tracer.start_turn(session.id, user_message)
        turn = TurnResult(session_id=session.id, trace_id=trace.trace_id, reply="")
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
                    return self._finish(turn, trace, started)

                session.append_assistant(b.to_dict(mode="json") for b in response.content)

                results = [self._run_tool(b.id, b.name, b.input, trace, turn) for b in tool_uses]
                session.append_tool_results(results)
        except Exception as exc:
            self._tracer.finish(trace, "", error=type(exc).__name__)
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
        self, tool_use_id: str, name: str, args: object, trace: Trace, turn: TurnResult
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        result = self._registry.dispatch(name, args)
        duration_ms = _ms_since(t0)
        trace.record_tool_call(name, args, result, duration_ms)
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

    def _finish(self, turn: TurnResult, trace: Trace, started: float) -> TurnResult:
        turn.latency_ms = _ms_since(started)
        self._tracer.finish(trace, turn.reply)
        return turn


def _final_reply(response: Message) -> str:
    if response.stop_reason == "refusal":
        return REFUSAL_REPLY
    text = "\n\n".join(b.text for b in response.content if b.type == "text").strip()
    return text or EMPTY_REPLY


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
