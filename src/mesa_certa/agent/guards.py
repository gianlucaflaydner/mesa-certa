"""Verificação da resposta antes de ela chegar ao cliente (SDD §8.5, camada P5).

Rede de segurança determinística para RN-07 e RN-12: se o modelo foi convencido a inventar
um código ou a confirmar o que nenhuma tool confirmou, a resposta é trocada.
"""

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from mesa_certa.domain.codes import ALPHABET
from mesa_certa.domain.rules import RESTAURANT_PHONE

SAFE_REPLY = (
    "Desculpe, não consegui confirmar essa informação no sistema de reservas. Para não passar "
    f"nada errado, fale com a equipe pelo telefone {RESTAURANT_PHONE}."
)

CREATE_TOOL = "criar_reserva"
GET_TOOL = "consultar_reserva"
CANCEL_TOOL = "cancelar_reserva"

_CODE_CHARS = re.escape(ALPHABET)
_CODE_TOKEN = re.compile(rf"(?<![A-Za-z0-9])[{_CODE_CHARS}]{{6}}(?![A-Za-z0-9])")
_CODE_WORD = re.compile(r"c[oó]digo", re.IGNORECASE)
_CODE_CONTEXT_CHARS = 20

_CREATION_CLAIMS = re.compile(
    r"\breserva (foi )?(criada|feita|realizada|efetuada|registrada)\b|\breservei\b",
)
_CONFIRMED_CLAIM = re.compile(r"\breserva (esta |foi |ficou )?confirmada\b")
_CANCEL_CLAIMS = re.compile(
    r"\bcancelei\b|\breserva (foi |esta |ficou )?cancelada\b|\bcancelamento (foi )?"
    r"(realizado|efetuado|feito|concluido)\b"
)


@dataclass(frozen=True)
class ToolOutcome:
    """Resumo de um `tool_result` do turno, no formato que as checagens precisam."""

    name: str
    ok: bool
    data: Mapping[str, Any] | None = None
    error_code: str | None = None


@dataclass
class GuardOutcome:
    reply: str
    violations: list[str] = field(default_factory=list)

    @property
    def replaced(self) -> bool:
        return bool(self.violations)


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _cited_codes(reply: str) -> set[str]:
    codes: set[str] = set()
    for match in _CODE_TOKEN.finditer(reply):
        token = match.group()
        window = reply[max(0, match.start() - _CODE_CONTEXT_CHARS) : match.start()]
        if any(ch.isdigit() for ch in token) or _CODE_WORD.search(window):
            codes.add(token)
    return codes


def _succeeded(outcomes: Iterable[ToolOutcome], name: str) -> list[ToolOutcome]:
    return [o for o in outcomes if o.name == name and o.ok]


_NEGATION = re.compile(r"\b(nao|nunca|ainda nao|sem)\b[^.!?\n]{0,15}$")


def _claims(pattern: re.Pattern[str], folded: str) -> bool:
    """Afirmação, não negação: "ainda não reservei" não conta."""
    return any(
        not _NEGATION.search(folded[max(0, m.start() - 25) : m.start()])
        for m in pattern.finditer(folded)
    )


def check_reply(reply: str, turn_outcomes: Iterable[ToolOutcome], known_text: str) -> GuardOutcome:
    """Checa (a) códigos citados e (b) confirmação sem tool.

    `known_text` reúne as mensagens do cliente e os `tool_result` da sessão: um código só é
    aceito se apareceu ali, ou seja, se não foi inventado pelo modelo.
    """
    outcomes = list(turn_outcomes)
    violations: list[str] = []

    known = known_text.upper()
    invented = sorted(code for code in _cited_codes(reply) if code not in known)
    if invented:
        violations.append(f"CODIGO_NAO_EMITIDO:{','.join(invented)}")

    folded = _fold(reply)
    created = bool(_succeeded(outcomes, CREATE_TOOL))
    if _claims(_CREATION_CLAIMS, folded) and not created:
        violations.append("CRIACAO_SEM_TOOL")
    if _claims(_CONFIRMED_CLAIM, folded) and not created and not _confirmed_by_lookup(outcomes):
        violations.append("CONFIRMACAO_SEM_TOOL")
    if _claims(_CANCEL_CLAIMS, folded) and not _cancel_confirmed(outcomes):
        violations.append("CANCELAMENTO_SEM_TOOL")

    return GuardOutcome(SAFE_REPLY if violations else reply, violations)


def _confirmed_by_lookup(outcomes: list[ToolOutcome]) -> bool:
    return any(
        (o.data or {}).get("situacao") == "CONFIRMADA" for o in _succeeded(outcomes, GET_TOOL)
    )


def _cancel_confirmed(outcomes: list[ToolOutcome]) -> bool:
    if _succeeded(outcomes, CANCEL_TOOL):
        return True
    # Reserva que já estava cancelada (RN-14), vista na consulta ou no erro do cancelamento.
    if any(o.name == CANCEL_TOOL and o.error_code == "JA_CANCELADA" for o in outcomes):
        return True
    return any(
        (o.data or {}).get("situacao") == "CANCELADA" for o in _succeeded(outcomes, GET_TOOL)
    )
