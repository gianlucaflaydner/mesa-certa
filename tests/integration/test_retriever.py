from pathlib import Path

import pytest

from mesa_certa.domain.date_resolver import FixedClock
from mesa_certa.rag.ingest import ingest_directory
from mesa_certa.rag.retriever import Retriever
from mesa_certa.rag.store import ChunkStore
from tests.fakes import HashingEmbedder
from tests.integration.conftest import at

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "knowledge"


@pytest.fixture
def indexed(tmp_path: Path) -> tuple[HashingEmbedder, ChunkStore]:
    embedder = HashingEmbedder()
    store = ChunkStore(tmp_path / "chroma", "teste")
    ingest_directory(FIXTURES, embedder, store, FixedClock(at(2026, 9, 15, 10)))
    return embedder, store


def make(indexed: tuple[HashingEmbedder, ChunkStore], **kwargs: float | int) -> Retriever:
    embedder, store = indexed
    options: dict[str, float | int] = {"top_k": 4, "similarity_threshold": 0.3} | kwargs
    return Retriever(
        embedder,
        store,
        top_k=int(options["top_k"]),
        similarity_threshold=float(options["similarity_threshold"]),
        max_context_chars=int(options.get("max_context_chars", 4000)),
    )


def test_busca_ordena_por_similaridade(indexed: tuple[HashingEmbedder, ChunkStore]) -> None:
    results = make(indexed).search("cachorros aceitos na varanda externa em coleira", top_k=5)

    assert results[0].chunk_id == "casa.md#animais>cachorros#0"
    assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)
    assert all(0.0 <= r.score <= 1.0 for r in results)
    assert len(results) == 5


def test_search_usa_prefixo_de_query_via_embedder(
    indexed: tuple[HashingEmbedder, ChunkStore],
) -> None:
    embedder, _ = indexed

    make(indexed).search("gatos")

    assert embedder.query_calls == ["gatos"]


def test_retrieve_aplica_limiar(indexed: tuple[HashingEmbedder, ChunkStore]) -> None:
    result = make(indexed, similarity_threshold=0.3).retrieve("gatos na varanda")

    assert not result.below_threshold
    assert result.chunks[0].chunk_id == "casa.md#animais>gatos#0"
    assert all(c.score >= 0.3 for c in result.chunks)


def test_nada_acima_do_limiar(indexed: tuple[HashingEmbedder, ChunkStore]) -> None:
    result = make(indexed, similarity_threshold=0.3).retrieve("feijoada quinta-feira")

    assert result.below_threshold
    assert result.chunks == []
    assert result.format_for_model() == ""


def test_top_k(indexed: tuple[HashingEmbedder, ChunkStore]) -> None:
    assert len(make(indexed, top_k=2).search("varanda")) == 2
    assert len(make(indexed).search("varanda", top_k=1)) == 1


def test_orcamento_de_contexto(indexed: tuple[HashingEmbedder, ChunkStore]) -> None:
    retriever = make(indexed, similarity_threshold=0.0, max_context_chars=150, top_k=5)

    result = retriever.retrieve("varanda externa coberta cachorros gatos")

    assert sum(len(c.content) for c in result.chunks) <= 150
    assert len(result.chunks) == 1


def test_primeiro_trecho_maior_que_o_orcamento_e_truncado(
    indexed: tuple[HashingEmbedder, ChunkStore],
) -> None:
    result = make(indexed, similarity_threshold=0.0, max_context_chars=40).retrieve("gatos")

    [chunk] = result.chunks
    assert len(chunk.content) == 40


def test_formato_de_citacao(indexed: tuple[HashingEmbedder, ChunkStore]) -> None:
    result = make(indexed, similarity_threshold=0.3, top_k=1).retrieve("gatos varanda")

    [chunk] = result.chunks
    assert chunk.citation == "casa.md › Animais › Gatos"
    assert result.format_for_model() == (
        f"[1] casa.md › Animais › Gatos (relevância {chunk.score:.2f})\n{chunk.content}"
    )


def test_indice_vazio(tmp_path: Path) -> None:
    retriever = Retriever(HashingEmbedder(), ChunkStore(tmp_path / "vazio", "teste"))

    assert retriever.search("qualquer") == []
    assert retriever.retrieve("qualquer").below_threshold
