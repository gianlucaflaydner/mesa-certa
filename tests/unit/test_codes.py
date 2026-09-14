import random

import pytest

from mesa_certa.domain import codes


def test_alfabeto_sem_ambiguos() -> None:
    assert len(codes.ALPHABET) == 32
    assert len(set(codes.ALPHABET)) == 32
    assert not set("0O1I") & set(codes.ALPHABET)
    assert codes.ALPHABET.upper() == codes.ALPHABET


def test_codigo_tem_6_caracteres_do_alfabeto() -> None:
    for _ in range(500):
        code = codes.generate_code()
        assert len(code) == 6
        assert set(code) <= set(codes.ALPHABET)


def test_rng_injetado_e_deterministico() -> None:
    assert codes.generate_code(random.Random(7)) == codes.generate_code(random.Random(7))


def test_retry_em_colisao() -> None:
    taken = ["AAAAAA", "BBBBBB"]
    calls: list[str] = []

    def is_taken(code: str) -> bool:
        calls.append(code)
        return len(calls) <= len(taken)

    code = codes.generate_unique_code(is_taken)
    assert len(calls) == 3
    assert code == calls[-1]


def test_desiste_apos_tentativas() -> None:
    with pytest.raises(codes.CodeGenerationError):
        codes.generate_unique_code(lambda _: True, max_attempts=5)


def test_normaliza_codigo() -> None:
    assert codes.normalize_code("  k7m2qp ") == "K7M2QP"
