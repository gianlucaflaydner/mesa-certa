"""Tool, envelope de resultado e geração do schema enviado ao modelo (SDD §7)."""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

ARGUMENTOS_INVALIDOS = "ARGUMENTOS_INVALIDOS"
ERRO_INTERNO = "ERRO_INTERNO"
TOOL_DESCONHECIDA = "TOOL_DESCONHECIDA"


@dataclass(frozen=True)
class ToolError:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    data: dict[str, Any] | None = None
    error: ToolError | None = None

    @classmethod
    def success(cls, data: Mapping[str, Any]) -> "ToolResult":
        return cls(ok=True, data=dict(data))

    @classmethod
    def failure(
        cls, code: str, message: str, details: Mapping[str, Any] | None = None
    ) -> "ToolResult":
        return cls(ok=False, error=ToolError(code, message, dict(details or {})))

    def to_dict(self) -> dict[str, Any]:
        if self.ok:
            return {"ok": True, "data": self.data}
        assert self.error is not None
        return {
            "ok": False,
            "error": {
                "code": self.error.code,
                "message": self.error.message,
                "details": self.error.details,
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


@dataclass(frozen=True)
class Tool[InputT: BaseModel]:
    name: str
    description: str
    input_model: type[InputT]
    handler: Callable[[InputT], Mapping[str, Any]]

    def input_schema(self) -> dict[str, Any]:
        return model_input_schema(self.input_model)

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema(),
        }


def model_input_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Schema JSON enxuto: sem `title`, sem `default` e com opcionais sem `anyOf` nulo."""
    raw = model.model_json_schema()
    properties: dict[str, Any] = {}
    for name, spec in raw.get("properties", {}).items():
        prop = {k: v for k, v in spec.items() if k not in {"title", "default", "anyOf"}}
        variants = [v for v in spec.get("anyOf", []) if v.get("type") != "null"]
        if variants:
            prop = {**variants[0], **prop}
        properties[name] = prop
    return {"type": "object", "properties": properties, "required": raw.get("required", [])}
