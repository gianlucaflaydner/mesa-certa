import pytest

from mesa_certa.observability.masking import (
    mask_email,
    mask_name,
    mask_phone,
    mask_text,
    mask_value,
)


def test_exemplos_do_sdd() -> None:
    assert mask_phone("11988887777") == "11*******77"
    assert mask_email("bruna@gmail.com") == "br***@gmail.com"
    assert mask_name("Bruna Alves") == "Bruna A."


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("(51) 98888-7777", "51*******77"),
        ("+55 51 98888-7777", "51*******77"),
        ("5130304050", "51******50"),
        ("123", "***"),
    ],
)
def test_telefone_em_formatos_variados(entrada: str, esperado: str) -> None:
    assert mask_phone(entrada) == esperado


def test_nome_com_varias_partes_usa_ultimo_sobrenome() -> None:
    assert mask_name("Roberto Carlos Lima") == "Roberto L."
    assert mask_name("  Camila ") == "Camila"


def test_email_invalido_vira_asteriscos() -> None:
    assert mask_email("sem-arroba") == "***"


def test_texto_livre_mascara_telefone_e_email() -> None:
    texto = "Sou a Bruna, telefone (51) 98888-7777 e e-mail bruna.alves@gmail.com."

    mascarado = mask_text(texto)

    assert "98888" not in mascarado
    assert "7777" not in mascarado
    assert "bruna.alves@" not in mascarado
    assert "51*******77" in mascarado
    assert "br***@gmail.com" in mascarado


def test_telefone_do_restaurante_nao_e_mascarado() -> None:
    texto = "Ligue para (51) 3030-4050."

    assert mask_text(texto) == texto


def test_texto_sem_dado_pessoal_fica_igual() -> None:
    texto = "Mesa para 6 pessoas no dia 2026-09-19 às 20:00, código K7M2QP."

    assert mask_text(texto) == texto


def test_mask_value_percorre_estrutura_por_nome_de_campo() -> None:
    dados = {
        "nome": "Bruna Alves",
        "telefone": "51988887777",
        "email": "bruna@gmail.com",
        "num_pessoas": 2,
        "observacoes": "ligar em 51977776666 se atrasar",
        "trechos": [{"conteudo": "contato bruna@gmail.com"}],
    }

    mascarado = mask_value(dados)

    assert mascarado == {
        "nome": "Bruna A.",
        "telefone": "51*******77",
        "email": "br***@gmail.com",
        "num_pessoas": 2,
        "observacoes": "ligar em 51*******66 se atrasar",
        "trechos": [{"conteudo": "contato br***@gmail.com"}],
    }
    assert dados["telefone"] == "51988887777"
