"""Sinalização de possível injeção de instruções (SDD §8.5, camada P6).

Só observa: o resultado vai para o trace e nunca muda o atendimento. Um cliente que escreve
"pode ignorar o que eu disse" não pode ser recusado por causa desta heurística.
"""

import re
import unicodedata

_PATTERNS = [
    r"\bignor[ea]\w*\b.{0,40}\b(instru\w*|regras?|orienta\w*|prompt)",
    r"\bignore (all |the )?previous instructions\b",
    r"\binstru\w* anteriores\b",
    r"\bsystem prompt\b",
    r"\bprompt do sistema\b",
    r"\bvoce agora e\b",
    r"\ba partir de agora voce e\b",
    r"\bmodo (desenvolvedor|developer|admin\w*)\b",
    r"\bjailbreak\b",
    r"^\s*(system|sistema|assistente|assistant)\s*:",
]
_REGEX = re.compile("|".join(f"(?:{p})" for p in _PATTERNS), re.IGNORECASE | re.MULTILINE)
# Troca de dígitos por letras parecidas, comum para escapar de filtros ("ign0re").
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a"})


def _fold(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return ascii_text.lower().translate(_LEET)


def looks_like_injection(text: str) -> bool:
    return bool(text) and _REGEX.search(_fold(text)) is not None
