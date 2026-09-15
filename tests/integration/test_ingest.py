import shutil
from collections.abc import Sequence
from pathlib import Path

import pytest

from mesa_certa.domain.date_resolver import FixedClock
from mesa_certa.rag.ingest import IngestReport, ingest_directory
from mesa_certa.rag.store import ChunkStore, MetadataValue
from tests.fakes import HashingEmbedder
from tests.integration.conftest import at

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "knowledge"
ALL_IDS = {
    "bebidas.md#vinhos#0",
    "bebidas.md#cafes#0",
    "casa.md#animais>cachorros#0",
    "casa.md#animais>gatos#0",
    "casa.md#estacionamento>convenio#0",
}


class SpyStore(ChunkStore):
    def __init__(self, path: Path, collection_name: str) -> None:
        super().__init__(path, collection_name)
        self.writes: list[str] = []

    def upsert(
        self,
        ids: Sequence[str],
        documents: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[dict[str, MetadataValue]],  # type: ignore[override]
    ) -> None:
        self.writes.append("upsert")
        super().upsert(ids, documents, embeddings, metadatas)

    def delete(self, ids: Sequence[str]) -> None:
        self.writes.append("delete")
        super().delete(ids)


@pytest.fixture
def knowledge(tmp_path: Path) -> Path:
    target = tmp_path / "knowledge"
    shutil.copytree(FIXTURES, target)
    return target


@pytest.fixture
def store(tmp_path: Path) -> SpyStore:
    return SpyStore(tmp_path / "chroma", "teste")


@pytest.fixture
def embedder() -> HashingEmbedder:
    return HashingEmbedder()


def run(knowledge: Path, embedder: HashingEmbedder, store: SpyStore) -> IngestReport:
    return ingest_directory(knowledge, embedder, store, FixedClock(at(2026, 9, 15, 10)))


def test_primeira_ingestao_cria_tudo(
    knowledge: Path, embedder: HashingEmbedder, store: SpyStore
) -> None:
    report = run(knowledge, embedder, store)

    assert set(report.created) == ALL_IDS
    assert report.updated == report.removed == report.unchanged == ()
    assert store.count() == len(ALL_IDS)
    assert all(text.startswith(("Bebidas", "Regras")) for text in embedder.passage_calls[0])


def test_metadados_gravados(knowledge: Path, embedder: HashingEmbedder, store: SpyStore) -> None:
    run(knowledge, embedder, store)

    [match] = [
        m
        for m in store.query(HashingEmbedder._vector("gatos"), 5)
        if m.chunk_id == "casa.md#animais>gatos#0"
    ]
    assert match.metadata["source"] == "casa.md"
    assert match.metadata["section_path"] == "Animais > Gatos"
    assert match.metadata["doc_title"] == "Regras da casa | Fixture"
    assert match.metadata["indexed_at"] == "2026-09-15T10:00:00-03:00"
    assert match.metadata["char_count"] == len(match.content)
    assert match.content.startswith("Gatos não são aceitos")


def test_segunda_execucao_sem_mudanca_faz_zero_escritas(
    knowledge: Path, embedder: HashingEmbedder, store: SpyStore
) -> None:
    run(knowledge, embedder, store)
    store.writes.clear()
    embedder.passage_calls.clear()

    report = run(knowledge, embedder, store)

    assert report.writes == 0
    assert set(report.unchanged) == ALL_IDS
    assert store.writes == []
    assert embedder.passage_calls == []


def test_editar_um_arquivo_atualiza_so_os_chunks_dele(
    knowledge: Path, embedder: HashingEmbedder, store: SpyStore
) -> None:
    run(knowledge, embedder, store)
    embedder.passage_calls.clear()
    casa = knowledge / "casa.md"
    casa.write_text(
        casa.read_text(encoding="utf-8").replace("cinquenta metros", "cem metros"),
        encoding="utf-8",
    )

    report = run(knowledge, embedder, store)

    assert report.updated == ("casa.md#estacionamento>convenio#0",)
    assert report.created == report.removed == ()
    assert set(report.unchanged) == ALL_IDS - {"casa.md#estacionamento>convenio#0"}
    assert len(embedder.passage_calls) == 1
    assert len(embedder.passage_calls[0]) == 1


def test_secao_e_arquivo_removidos_saem_do_indice(
    knowledge: Path, embedder: HashingEmbedder, store: SpyStore
) -> None:
    run(knowledge, embedder, store)
    (knowledge / "bebidas.md").unlink()

    report = run(knowledge, embedder, store)

    assert set(report.removed) == {"bebidas.md#vinhos#0", "bebidas.md#cafes#0"}
    assert store.count() == 3
    assert set(store.hashes()) == ALL_IDS - set(report.removed)


def test_resumo(knowledge: Path, embedder: HashingEmbedder, store: SpyStore) -> None:
    report = run(knowledge, embedder, store)

    assert report.summary() == "criados: 5, atualizados: 0, removidos: 0, inalterados: 0"
