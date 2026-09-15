"""Registry das tools (SDD §7.7).

`dispatch` nunca levanta exceção: todo erro volta como envelope, para que o modelo possa
se recuperar na mesma conversa.
"""

import logging
import time
from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import ValidationError

from mesa_certa.domain.errors import DomainError
from mesa_certa.tools.base import (
    ARGUMENTOS_INVALIDOS,
    ERRO_INTERNO,
    TOOL_DESCONHECIDA,
    Tool,
    ToolResult,
)

logger = logging.getLogger(__name__)


class ToolCallObserver(Protocol):
    """Gancho para o trace da F4: recebe cada chamada já concluída."""

    def on_tool_call(
        self, name: str, args: object, result: ToolResult, duration_ms: float
    ) -> None: ...


class ToolRegistry:
    def __init__(self, observer: ToolCallObserver | None = None) -> None:
        self._tools: dict[str, Tool[Any]] = {}
        self.observer = observer

    def register(self, tool: Tool[Any]) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool já registrada: {tool.name}")
        self._tools[tool.name] = tool

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def dispatch(self, name: str, args: object) -> ToolResult:
        started = time.perf_counter()
        result = self._run(name, args)
        if self.observer is not None:
            duration_ms = (time.perf_counter() - started) * 1000
            try:
                self.observer.on_tool_call(name, args, result, duration_ms)
            except Exception:
                logger.exception("Falha no observador da tool %s", name)
        return result

    def _run(self, name: str, args: object) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult.failure(
                TOOL_DESCONHECIDA,
                f"A tool '{name}' não existe.",
                {"tools_disponiveis": self.names},
            )
        try:
            params = tool.input_model.model_validate(args if args is not None else {})
            return ToolResult.success(tool.handler(params))
        except ValidationError as exc:
            return ToolResult.failure(
                ARGUMENTOS_INVALIDOS,
                "Argumentos inválidos para a tool.",
                {"erros": _validation_errors(exc)},
            )
        except DomainError as exc:
            return ToolResult.failure(exc.code, exc.message, exc.details)
        except Exception:
            logger.exception("Erro inesperado na tool %s", name)
            return ToolResult.failure(
                ERRO_INTERNO, "Erro interno ao executar a tool. Tente novamente."
            )


def _validation_errors(exc: ValidationError) -> list[Mapping[str, str]]:
    return [
        {
            "campo": ".".join(str(part) for part in error["loc"]) or "(raiz)",
            "mensagem": error["msg"],
        }
        for error in exc.errors(include_url=False, include_input=False)
    ]
