"""Código de reserva (RN-12, SDD §5.7)."""

import random
import secrets
from collections.abc import Callable

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0, O, 1, I
LENGTH = 6
MAX_ATTEMPTS = 5


class CodeGenerationError(RuntimeError):
    pass


def generate_code(rng: random.Random | None = None) -> str:
    choose = rng.choice if rng is not None else secrets.choice
    return "".join(choose(ALPHABET) for _ in range(LENGTH))


def generate_unique_code(
    is_taken: Callable[[str], bool],
    rng: random.Random | None = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> str:
    for _ in range(max_attempts):
        code = generate_code(rng)
        if not is_taken(code):
            return code
    raise CodeGenerationError(f"Nenhum código livre em {max_attempts} tentativas")


def normalize_code(code: str) -> str:
    return code.strip().upper()
