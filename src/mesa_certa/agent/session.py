"""Histórico de conversa em memória (SDD §8.4, RF-08).

A poda acontece no início de cada turno e nunca começa o histórico por um `tool_result`,
que ficaria órfão do `tool_use` que o originou e seria rejeitado pela API.
"""

import threading
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from mesa_certa.domain.date_resolver import Clock

Message = dict[str, Any]


class SessionExpired(Exception):
    """Sessão desconhecida ou inativa além do TTL."""

    def __init__(self, session_id: str) -> None:
        super().__init__(f"Sessão expirada ou inexistente: {session_id}")
        self.session_id = session_id


def _is_turn_start(message: Mapping[str, Any]) -> bool:
    if message.get("role") != "user":
        return False
    content = message.get("content")
    if isinstance(content, str):
        return True
    return not any(
        isinstance(block, Mapping) and block.get("type") == "tool_result" for block in content or []
    )


@dataclass
class Session:
    id: str
    last_activity: datetime
    max_messages: int = 20
    messages: list[Message] = field(default_factory=list)
    # Um turno por vez por sessão: dois pedidos simultâneos embaralhariam o histórico.
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def append_user(self, text: str) -> None:
        self._prune(keep=self.max_messages - 1)
        self.messages.append({"role": "user", "content": text})

    def append_assistant(self, content: Iterable[Mapping[str, Any]]) -> None:
        self.messages.append({"role": "assistant", "content": [dict(b) for b in content]})

    def append_tool_results(self, results: Iterable[Mapping[str, Any]]) -> None:
        self.messages.append({"role": "user", "content": [dict(r) for r in results]})

    def to_api_messages(self) -> list[Message]:
        return [dict(m) for m in self.messages]

    def replace_last_reply(self, text: str) -> None:
        """Troca a resposta final do turno (usado pela verificação da resposta, SDD §8.5).

        Só atua sobre uma mensagem final, sem `tool_use`; os blocos de thinking dela podem
        sair, porque a API só exige thinking dentro de um ciclo de tool em andamento.
        """
        if self.messages and self.messages[-1].get("role") == "assistant":
            self.messages[-1] = {"role": "assistant", "content": [{"type": "text", "text": text}]}

    def customer_and_tool_text(self) -> str:
        """Tudo que o cliente escreveu e que as tools devolveram nesta sessão."""
        parts: list[str] = []
        for message in self.messages:
            if message.get("role") != "user":
                continue
            content = message.get("content")
            if isinstance(content, str):
                parts.append(content)
                continue
            parts.extend(
                str(block.get("content", ""))
                for block in content or []
                if isinstance(block, Mapping) and block.get("type") == "tool_result"
            )
        return "\n".join(parts)

    def _prune(self, keep: int) -> None:
        if len(self.messages) <= keep:
            return
        window = self.messages[-keep:] if keep > 0 else []
        start = next((i for i, m in enumerate(window) if _is_turn_start(m)), len(window))
        self.messages = window[start:]


class SessionStore:
    def __init__(self, clock: Clock, ttl_minutes: int = 60, max_messages: int = 20) -> None:
        self._clock = clock
        self._ttl = timedelta(minutes=ttl_minutes)
        self._max_messages = max_messages
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self) -> Session:
        session = Session(
            id=str(uuid.uuid4()), last_activity=self._clock.now(), max_messages=self._max_messages
        )
        with self._lock:
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session:
        """Devolve a sessão e renova a atividade. Levanta `SessionExpired` se não houver."""
        now = self._clock.now()
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or now - session.last_activity > self._ttl:
                self._sessions.pop(session_id, None)
                raise SessionExpired(session_id)
            session.last_activity = now
            return session

    def get_or_create(self, session_id: str | None) -> Session:
        return self.create() if session_id is None else self.get(session_id)

    def purge_expired(self) -> int:
        now = self._clock.now()
        with self._lock:
            expired = [s for s, v in self._sessions.items() if now - v.last_activity > self._ttl]
            for session_id in expired:
                del self._sessions[session_id]
        return len(expired)
