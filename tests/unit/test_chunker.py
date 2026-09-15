from itertools import pairwise
from pathlib import Path

import pytest

from mesa_certa.rag import chunker
from mesa_certa.rag.chunker import Chunk, chunk_directory, chunk_document, slug

KNOWLEDGE = Path(__file__).resolve().parents[2] / "data" / "knowledge"
FILLER = "Texto de preenchimento com tamanho suficiente para não ser fundido ao vizinho seguinte."


def ids(chunks: list[Chunk]) -> list[str]:
    return [c.chunk_id for c in chunks]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Opções sem glúten", "opcoes-sem-gluten"),
        ("Alérgenos: pratos principais", "alergenos-pratos-principais"),
        ("Alérgenos, pratos principais", "alergenos-pratos-principais"),
        ("Vocês têm opções sem glúten?", "voces-tem-opcoes-sem-gluten"),
        ("  --Perdi meu código. E agora?!  ", "perdi-meu-codigo-e-agora"),
        ("Telefone e e-mail", "telefone-e-e-mail"),
    ],
)
def test_slug(text: str, expected: str) -> None:
    assert slug(text) == expected


def test_h2_sem_h3_e_preambulo_ignorado() -> None:
    doc = f"# Doc\n\nPreâmbulo.\n\n## Sobremesas\n\n{FILLER}\n"

    [chunk] = chunk_document("cardapio.md", doc)

    assert chunk.chunk_id == "cardapio.md#sobremesas#0"
    assert chunk.section_path == "Sobremesas"
    assert "Preâmbulo" not in chunk.content


def test_h3_e_texto_para_embedding() -> None:
    doc = f"# Cardápio | Mesa Certa\n\n## Pratos principais\n\n### Opções sem glúten\n\n{FILLER}"

    [chunk] = chunk_document("cardapio.md", doc)

    assert chunk.chunk_id == "cardapio.md#pratos-principais>opcoes-sem-gluten#0"
    assert chunk.section_label == "Pratos principais › Opções sem glúten"
    assert chunk.text == (
        f"Cardápio | Mesa Certa > Pratos principais > Opções sem glúten\n\n{FILLER}"
    )
    assert chunk.char_count == len(FILLER)
    assert len(chunk.content_hash) == 64


def test_hash_muda_com_o_cabecalho() -> None:
    base = f"# Doc\n\n## Seção\n\n{FILLER}"
    renamed = f"# Doc\n\n## Seção renomeada\n\n{FILLER}"

    assert chunk_document("a.md", base)[0].content_hash != (
        chunk_document("a.md", renamed)[0].content_hash
    )


def test_intro_do_h2_vira_chunk_proprio() -> None:
    doc = f"# Doc\n\n## Bebidas\n\n{FILLER}\n\n### Vinhos\n\n{FILLER}"

    assert ids(chunk_document("c.md", doc)) == ["c.md#bebidas#0", "c.md#bebidas>vinhos#0"]


def test_secao_pequena_funde_no_irmao_seguinte() -> None:
    doc = (
        "# FAQ\n\n## No restaurante\n\n"
        "### Tem manobrista?\n\nNão.\n\n"
        f"### Tem delivery?\n\n{FILLER}\n"
    )

    [chunk] = chunk_document("faq.md", doc)

    assert chunk.chunk_id == "faq.md#no-restaurante>tem-delivery#0"
    assert chunk.content.startswith("Tem manobrista?\n\nNão.\n\n")
    assert chunk.content.endswith(FILLER)


def test_fusao_em_cadeia() -> None:
    doc = "# D\n\n## S\n\n### A\n\nUm.\n\n### B\n\nDois.\n\n" + f"### C\n\n{FILLER}"

    [chunk] = chunk_document("d.md", doc)

    assert chunk.chunk_id == "d.md#s>c#0"
    assert chunk.content.startswith("A\n\nUm.\n\nB\n\nDois.")


def test_pequena_sem_irmao_seguinte_fica_sozinha() -> None:
    doc = f"# D\n\n## S\n\n### A\n\n{FILLER}\n\n### Fim\n\nCurto.\n\n## Outra\n\n{FILLER}"

    assert ids(chunk_document("d.md", doc)) == ["d.md#s>a#0", "d.md#s>fim#0", "d.md#outra#0"]


def test_divisao_por_paragrafo_com_sobreposicao() -> None:
    paragraphs = [f"Parágrafo {i}. " + "x" * 400 for i in range(4)]
    doc = "# D\n\n## Longa\n\n" + "\n\n".join(paragraphs)

    chunks = chunk_document("d.md", doc)

    assert ids(chunks) == ["d.md#longa#0", "d.md#longa#1", "d.md#longa#2"]
    assert all(len(c.content) <= chunker.MAX_CHARS for c in chunks)
    for previous, current in pairwise(chunks):
        last_paragraph = previous.content.split("\n\n")[-1]
        assert current.content.startswith(last_paragraph)


def test_tabela_nunca_e_partida() -> None:
    rows = "\n".join(f"| Prato {i} | Sim | Não | Não | Não |" for i in range(60))
    header = "| Prato | Glúten | Lactose | Castanhas | Frutos do mar |\n|---|---|---|---|---|"
    table = f"{header}\n{rows}"
    doc = f"# D\n\n## Alérgenos\n\n{FILLER}\n\n{table}\n\n{FILLER}"

    chunks = chunk_document("d.md", doc)

    holders = [c for c in chunks if "| Prato 0 |" in c.content]
    assert holders
    assert all(table in c.content for c in holders)


def test_cabecalho_em_bloco_de_codigo_nao_abre_secao() -> None:
    doc = f"# D\n\n## Real\n\n{FILLER}\n\n```\n## falso\n```\n"

    assert ids(chunk_document("d.md", doc)) == ["d.md#real#0"]


def test_documento_sem_titulo() -> None:
    with pytest.raises(ValueError, match="Título"):
        chunk_document("x.md", f"## Seção\n\n{FILLER}")


def test_chunk_id_duplicado() -> None:
    doc = f"# D\n\n## Seção\n\n{FILLER}\n\n## Seção!\n\n{FILLER}"

    with pytest.raises(ValueError, match="duplicado"):
        chunk_document("d.md", doc)


def test_base_real_tem_ids_unicos_e_ordenados_por_arquivo() -> None:
    chunks = chunk_directory(KNOWLEDGE)

    assert len(set(ids(chunks))) == len(chunks)
    assert [c.source for c in chunks] == sorted(c.source for c in chunks)
    assert {c.source for c in chunks} == {"cardapio.md", "faq.md", "politicas.md", "sobre.md"}
