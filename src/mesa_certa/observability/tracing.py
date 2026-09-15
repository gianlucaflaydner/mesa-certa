"""Trace estruturado por turno (SDD §10.1, RF-13).

Todo texto e argumento passa por `masking` no momento do registro, então nada que sai
daqui (arquivo JSONL, log ou endpoint de debug) carrega dado pessoal sem máscara.
"""

import json
import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from mesa_certa.domain.date_resolver import Clock
from mesa_certa.observability.injection import looks_like_injection
from mesa_certa.observability.masking import mask_text, mask_value
from mesa_certa.tools.base import ToolResult
from mesa_certa.tools.reservations import CUSTOMER_DATA_KEY

logger = structlog.get_logger(__name__)

KNOWLEDGE_TOOL = "buscar_conhecimento"
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_MAX_TRACES_IN_MEMORY = 500


def new_ulid(timestamp_ms: int | None = None) -> str:
    """ULID: 48 bits de milissegundos e 80 aleatórios, em Crockford base32. Ordena por tempo."""
    ms = time.time_ns() // 1_000_000 if timestamp_ms is None else timestamp_ms
    value = (ms << 80) | secrets.randbits(80)
    return "".join(_CROCKFORD[(value >> shift) & 31] for shift in range(125, -1, -5))


@dataclass
class LLMCallSpan:
    iteration: int
    stop_reason: str | None
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    duration_ms: int


@dataclass
class ToolCallSpan:
    name: str
    args: Any
    ok: bool
    error_code: str | None
    duration_ms: int


@dataclass
class RetrievalSpan:
    query: str
    chunk_ids: list[str]
    scores: list[float]
    below_threshold: bool


@dataclass
class Trace:
    trace_id: str
    session_id: str
    started_at: datetime
    user_message: str
    finished_at: datetime | None = None
    llm_calls: list[LLMCallSpan] = field(default_factory=list)
    tool_calls: list[ToolCallSpan] = field(default_factory=list)
    retrievals: list[RetrievalSpan] = field(default_factory=list)
    final_reply: str = ""
    iterations: int = 0
    exhausted: bool = False
    stop_reason: str | None = None
    suspeita_injecao: bool = False
    guard_violations: list[str] = field(default_factory=list)
    error: str | None = None
    total_ms: int = 0
    _started_perf: float = field(default_factory=time.perf_counter, repr=False)

    def record_llm_call(
        self,
        iteration: int,
        stop_reason: str | None,
        input_tokens: int,
        output_tokens: int,
        cache_read_input_tokens: int,
        duration_ms: int,
    ) -> None:
        self.iterations = iteration
        self.stop_reason = stop_reason
        self.llm_calls.append(
            LLMCallSpan(
                iteration,
                stop_reason,
                input_tokens,
                output_tokens,
                cache_read_input_tokens,
                duration_ms,
            )
        )

    def record_tool_call(
        self, name: str, args: object, result: ToolResult, duration_ms: int
    ) -> None:
        self.tool_calls.append(
            ToolCallSpan(
                name=name,
                args=mask_value(args),
                ok=result.ok,
                error_code=result.error.code if result.error else None,
                duration_ms=duration_ms,
            )
        )
        if name == KNOWLEDGE_TOOL and result.ok and result.data is not None:
            self._record_retrieval(args, result.data)
        customer_data = (result.data or {}).get(CUSTOMER_DATA_KEY)
        if isinstance(customer_data, Mapping) and any(
            isinstance(v, str) and looks_like_injection(v) for v in customer_data.values()
        ):
            self.suspeita_injecao = True

    def _record_retrieval(self, args: object, data: Mapping[str, Any]) -> None:
        query = args.get("pergunta", "") if isinstance(args, Mapping) else ""
        chunks = data.get("trechos") or []
        self.retrievals.append(
            RetrievalSpan(
                query=mask_text(str(query)),
                chunk_ids=[str(c.get("chunk_id", "")) for c in chunks],
                scores=[float(c.get("relevancia", 0.0)) for c in chunks],
                below_threshold=not data.get("encontrou_informacao", False),
            )
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("_started_perf")
        return data


class Tracer:
    """Abre e fecha traces, grava JSONL diário e guarda os mais recentes para consulta."""

    def __init__(self, clock: Clock, trace_path: Path | None) -> None:
        self._clock = clock
        self._trace_path = trace_path
        self._recent: OrderedDict[str, Trace] = OrderedDict()
        self._lock = threading.Lock()

    def start_turn(self, session_id: str, user_message: str) -> Trace:
        return Trace(
            trace_id=new_ulid(),
            session_id=session_id,
            started_at=self._clock.now(),
            user_message=mask_text(user_message),
            suspeita_injecao=looks_like_injection(user_message),
        )

    def finish(self, trace: Trace, reply: str, error: str | None = None) -> None:
        trace.final_reply = mask_text(reply)
        trace.error = error
        trace.finished_at = self._clock.now()
        trace.total_ms = round((time.perf_counter() - trace._started_perf) * 1000)
        with self._lock:
            self._recent[trace.trace_id] = trace
            while len(self._recent) > _MAX_TRACES_IN_MEMORY:
                self._recent.popitem(last=False)
        self._write(trace)
        logger.info(
            "turno_concluido",
            trace_id=trace.trace_id,
            session_id=trace.session_id,
            iterations=trace.iterations,
            tools=[t.name for t in trace.tool_calls],
            exhausted=trace.exhausted,
            suspeita_injecao=trace.suspeita_injecao,
            guard_violations=trace.guard_violations,
            error=trace.error,
            total_ms=trace.total_ms,
        )

    def get(self, trace_id: str) -> Trace | None:
        with self._lock:
            return self._recent.get(trace_id)

    def _write(self, trace: Trace) -> None:
        if self._trace_path is None:
            return
        path = self._trace_path / f"{trace.started_at.date().isoformat()}.jsonl"
        line = json.dumps(trace.to_dict(), ensure_ascii=False, default=str)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            logger.exception("falha_ao_gravar_trace", trace_id=trace.trace_id)
