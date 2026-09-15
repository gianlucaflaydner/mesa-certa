"""Cliente do modelo injetável no loop.

`AnthropicLLM` isola o SDK: o loop só conhece `LLMClient`, e os testes usam um dublê
roteirizado sem rede. Falhas transitórias da API viram `ModelUnavailable` (HTTP 503 na F5).
"""

from collections.abc import Sequence
from typing import Any, Protocol, cast

import anthropic
from anthropic.types import Message, MessageParam, TextBlockParam, ToolParam

from mesa_certa.config import Effort


class ModelUnavailable(Exception):
    """API do modelo indisponível: rede, limite de taxa ou erro do servidor."""


class LLMClient(Protocol):
    def create(
        self,
        *,
        system: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
        messages: Sequence[dict[str, Any]],
    ) -> Message: ...


class AnthropicLLM:
    def __init__(
        self,
        client: anthropic.Anthropic,
        model: str,
        max_tokens: int = 16000,
        effort: Effort = "medium",
    ) -> None:
        self._client = client
        self.model = model
        self.max_tokens = max_tokens
        self.effort = effort

    def create(
        self,
        *,
        system: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
        messages: Sequence[dict[str, Any]],
    ) -> Message:
        try:
            return self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                output_config={"effort": self.effort},
                system=cast(list[TextBlockParam], list(system)),
                tools=cast(list[ToolParam], list(tools)),
                messages=cast(list[MessageParam], list(messages)),
            )
        except (anthropic.APIConnectionError, anthropic.RateLimitError) as exc:
            raise ModelUnavailable(str(exc)) from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                raise ModelUnavailable(str(exc)) from exc
            raise
