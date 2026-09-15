"""Higiene de texto vindo de terceiros (SDD §8.5, camadas P3 e P4).

Remove o que serve para esconder instrução (caracteres de controle e de largura zero) e
limita o tamanho. Não bloqueia palavras: isso recusaria clientes legítimos.
"""

import re
import unicodedata

MAX_MESSAGE_CHARS = 2000

_ZERO_WIDTH = frozenset({"​", "‌", "‍", "⁠", "﻿"})
_KEEP_CONTROL = frozenset({"\n", "\t"})
_WHITESPACE = re.compile(r"\s+")


class MessageTooLong(ValueError):
    def __init__(self, length: int, max_chars: int) -> None:
        super().__init__(f"Mensagem com {length} caracteres; o limite é {max_chars}.")
        self.length = length
        self.max_chars = max_chars


def clean_text(value: str) -> str:
    """Tira controle (menos quebra de linha e tab) e largura zero, e apara as pontas."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return "".join(
        ch
        for ch in normalized
        if ch not in _ZERO_WIDTH and (ch in _KEEP_CONTROL or unicodedata.category(ch) != "Cc")
    ).strip()


def clean_single_line(value: str) -> str:
    """Como `clean_text`, e ainda junta todo espaço em branco num único espaço.

    Usado em campos gravados no banco: sem quebra de linha, um texto não consegue imitar
    um cabeçalho como "SISTEMA:" em linha própria quando for devolvido ao modelo.
    """
    return _WHITESPACE.sub(" ", clean_text(value))


def clean_message(value: str, max_chars: int = MAX_MESSAGE_CHARS) -> str:
    cleaned = clean_text(value)
    if len(cleaned) > max_chars:
        raise MessageTooLong(len(cleaned), max_chars)
    return cleaned
