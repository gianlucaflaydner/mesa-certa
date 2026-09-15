from typing import Any

import anthropic
import httpx2
import pytest

from mesa_certa.agent.llm import AnthropicLLM, ModelUnavailable
from tests.fakes import text_response

_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


class _Messages:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> object:
        self.kwargs = kwargs
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class _Client:
    def __init__(self, outcome: object) -> None:
        self.messages = _Messages(outcome)


def _llm(outcome: object) -> tuple[AnthropicLLM, _Client]:
    client = _Client(outcome)
    return AnthropicLLM(client, "claude-sonnet-5", 16000, "low"), client  # type: ignore[arg-type]


def _status_error(cls: type[anthropic.APIStatusError], status: int) -> anthropic.APIStatusError:
    return cls("erro", response=httpx2.Response(status, request=_REQUEST), body=None)


def test_envia_modelo_effort_e_nao_envia_temperature() -> None:
    llm, client = _llm(text_response("oi"))

    llm.create(system=[{"type": "text", "text": "s"}], tools=[], messages=[])

    kwargs = client.messages.kwargs
    assert kwargs["model"] == "claude-sonnet-5"
    assert kwargs["max_tokens"] == 16000
    assert kwargs["output_config"] == {"effort": "low"}
    assert "temperature" not in kwargs


@pytest.mark.parametrize(
    "erro",
    [
        anthropic.APIConnectionError(request=_REQUEST),
        anthropic.APITimeoutError(request=_REQUEST),
        _status_error(anthropic.RateLimitError, 429),
        _status_error(anthropic.InternalServerError, 500),
        _status_error(anthropic.APIStatusError, 529),
    ],
)
def test_falhas_transitorias_viram_model_unavailable(erro: Exception) -> None:
    llm, _ = _llm(erro)

    with pytest.raises(ModelUnavailable):
        llm.create(system=[], tools=[], messages=[])


def test_erro_de_requisicao_nao_e_mascarado() -> None:
    llm, _ = _llm(_status_error(anthropic.BadRequestError, 400))

    with pytest.raises(anthropic.BadRequestError):
        llm.create(system=[], tools=[], messages=[])
