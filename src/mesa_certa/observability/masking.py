"""Mascaramento de dados pessoais antes de qualquer escrita em log ou trace (SDD §10.2, RN-15)."""

import re
from collections.abc import Mapping
from typing import Any

from mesa_certa.domain.rules import RESTAURANT_PHONE

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Celular ou fixo brasileiro com DDD, com ou sem +55, parênteses, espaço, ponto ou hífen.
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?55[\s.-]?)?\(?\d{2}\)?[\s.-]?9?\d{4}[\s.-]?\d{4}(?!\d)")
_DIGITS_RE = re.compile(r"\D")
_PUBLIC_PHONES = frozenset({_DIGITS_RE.sub("", RESTAURANT_PHONE)})

_PHONE_KEYS = frozenset({"telefone", "customer_phone", "phone"})
_EMAIL_KEYS = frozenset({"email", "customer_email"})
_NAME_KEYS = frozenset({"nome", "customer_name", "name"})


def mask_phone(value: str) -> str:
    """Mantém DDD e os 2 últimos dígitos: `11988887777` vira `11*******77`."""
    digits = _DIGITS_RE.sub("", value)
    if len(digits) > 11 and digits.startswith("55"):
        digits = digits[2:]
    if len(digits) < 6:
        return "*" * len(digits)
    return f"{digits[:2]}{'*' * (len(digits) - 4)}{digits[-2:]}"


def mask_email(value: str) -> str:
    """Mantém os 2 primeiros caracteres e o domínio: `bruna@gmail.com` vira `br***@gmail.com`."""
    local, sep, domain = value.partition("@")
    if not sep:
        return "***"
    return f"{local[:2]}***@{domain}"


def mask_name(value: str) -> str:
    """Mantém o primeiro nome e a inicial do sobrenome: `Bruna Alves` vira `Bruna A.`."""
    parts = value.split()
    if len(parts) < 2:
        return value.strip()
    return f"{parts[0]} {parts[-1][0]}."


def mask_text(text: str) -> str:
    """Mascara e-mails e telefones em texto livre. O telefone do restaurante é público."""
    text = _EMAIL_RE.sub(lambda m: mask_email(m.group()), text)

    def _phone(match: re.Match[str]) -> str:
        digits = _DIGITS_RE.sub("", match.group())
        if digits in _PUBLIC_PHONES or digits.removeprefix("55") in _PUBLIC_PHONES:
            return match.group()
        return mask_phone(match.group())

    return _PHONE_RE.sub(_phone, text)


def mask_value(value: Any, key: str | None = None) -> Any:
    """Mascara recursivamente dicts e listas, por nome de campo e por padrão no texto."""
    if isinstance(value, Mapping):
        return {k: mask_value(v, str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [mask_value(item, key) for item in value]
    if not isinstance(value, str):
        return value
    if key in _PHONE_KEYS:
        return mask_phone(value)
    if key in _EMAIL_KEYS:
        return mask_email(value)
    if key in _NAME_KEYS:
        return mask_name(value)
    return mask_text(value)
