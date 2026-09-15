"""Dublês de teste compartilhados."""

import copy
import hashlib
import math
import re
import unicodedata
from collections.abc import Sequence
from typing import Any

from anthropic.types import Message

from mesa_certa.rag.embedder import QUERY_PREFIX

DIMENSIONS = 384
_WORD = re.compile(r"[a-z0-9]+")


class HashingEmbedder:
    """Bag of words com hashing: determinístico, sem rede, similaridade por palavras em comum."""

    def __init__(self) -> None:
        self.query_calls: list[str] = []
        self.passage_calls: list[list[str]] = []

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return self._vector(text)

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        self.passage_calls.append(list(texts))
        return [self._vector(t) for t in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
        vector = [0.0] * DIMENSIONS
        for word in _WORD.findall(folded):
            index = int(hashlib.md5(word.encode()).hexdigest(), 16) % DIMENSIONS
            vector[index] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class RecordingModel:
    """Imita `SentenceTransformer.encode` e guarda o que recebeu."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def encode(self, sentences: list[str], **kwargs: object) -> list[list[float]]:
        self.calls.append((list(sentences), kwargs))
        return [[1.0 if s.startswith(QUERY_PREFIX) else 0.0, 1.0] for s in sentences]


def _message(content: list[dict[str, Any]], stop_reason: str) -> Message:
    return Message.model_validate(
        {
            "id": "msg_teste",
            "type": "message",
            "role": "assistant",
            "model": "claude-teste",
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 80},
        }
    )


def text_response(text: str, stop_reason: str = "end_turn") -> Message:
    return _message([{"type": "text", "text": text}], stop_reason)


def tool_response(*calls: tuple[str, dict[str, Any]], text: str | None = None) -> Message:
    """Resposta pedindo tools; ids `toolu_1`, `toolu_2`... na ordem dos pedidos."""
    content: list[dict[str, Any]] = [{"type": "text", "text": text}] if text else []
    content += [
        {"type": "tool_use", "id": f"toolu_{i}", "name": name, "input": args}
        for i, (name, args) in enumerate(calls, start=1)
    ]
    return _message(content, "tool_use")


class ScriptedLLM:
    """Devolve as respostas roteirizadas em ordem e guarda cópia de cada requisição."""

    def __init__(self, *responses: Message | Exception, repeat_last: bool = False) -> None:
        self._responses = list(responses)
        self._repeat_last = repeat_last
        self.requests: list[dict[str, Any]] = []

    def create(
        self,
        *,
        system: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
        messages: Sequence[dict[str, Any]],
    ) -> Message:
        self.requests.append(
            copy.deepcopy(
                {"system": list(system), "tools": list(tools), "messages": list(messages)}
            )
        )
        if not self._responses:
            raise AssertionError("ScriptedLLM sem respostas restantes")
        item = self._responses[0] if self._repeat_last and len(self._responses) == 1 else None
        if item is None:
            item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
