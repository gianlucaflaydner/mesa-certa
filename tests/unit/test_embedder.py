import math

import pytest

from mesa_certa.config import Settings
from mesa_certa.rag.embedder import Embedder
from tests.fakes import RecordingModel


def test_prefixo_de_query() -> None:
    model = RecordingModel()

    Embedder("qualquer", model=model).embed_query("tem opção sem glúten?")

    [(sentences, kwargs)] = model.calls
    assert sentences == ["query: tem opção sem glúten?"]
    assert kwargs["normalize_embeddings"] is True


def test_prefixo_de_passagem() -> None:
    model = RecordingModel()

    vectors = Embedder("qualquer", model=model).embed_passages(["a", "b"])

    [(sentences, _)] = model.calls
    assert sentences == ["passage: a", "passage: b"]
    assert vectors == [[0.0, 1.0], [0.0, 1.0]]


def test_lista_vazia_nao_chama_o_modelo() -> None:
    model = RecordingModel()

    assert Embedder("qualquer", model=model).embed_passages([]) == []
    assert model.calls == []


@pytest.mark.slow
def test_modelo_real(settings: Settings) -> None:
    embedder = Embedder(settings.embedding_model)

    query = embedder.embed_query("opções sem glúten")
    passage, other = embedder.embed_passages(["Pratos sem glúten", "Taxa de rolha do vinho"])

    assert len(query) == 384
    assert math.isclose(math.fsum(v * v for v in query), 1.0, rel_tol=1e-4)

    def cosine(a: list[float], b: list[float]) -> float:
        return math.fsum(x * y for x, y in zip(a, b, strict=True))

    assert cosine(query, passage) > cosine(query, other)
    assert query != embedder.embed_passages(["opções sem glúten"])[0]
