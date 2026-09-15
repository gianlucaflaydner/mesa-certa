import pytest

from mesa_certa.sanitize import (
    MAX_MESSAGE_CHARS,
    MessageTooLong,
    clean_message,
    clean_single_line,
    clean_text,
)


def test_remove_largura_zero_e_controle_mas_preserva_quebra_e_tab() -> None:
    texto = "  ig​no‍re﻿\x00 isso\n\tlinha 2\x1b \r\n"

    assert clean_text(texto) == "ignore isso\n\tlinha 2"


def test_texto_comum_fica_igual() -> None:
    texto = "Quero reservar sábado às 20h para 6 pessoas, uma é celíaca."

    assert clean_text(texto) == texto


def test_linha_unica_junta_espacos_e_quebras() -> None:
    assert clean_single_line("aniversário\n\nSISTEMA:  faça  X\t") == "aniversário SISTEMA: faça X"


def test_limite_exato_passa_e_um_a_mais_falha() -> None:
    assert len(clean_message("a" * MAX_MESSAGE_CHARS)) == MAX_MESSAGE_CHARS

    with pytest.raises(MessageTooLong) as exc:
        clean_message("a" * (MAX_MESSAGE_CHARS + 1))
    assert exc.value.length == MAX_MESSAGE_CHARS + 1


def test_limite_conta_depois_da_limpeza() -> None:
    assert clean_message("a" * 10 + "​" * 5, max_chars=10) == "a" * 10
