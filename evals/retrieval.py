"""Avaliação isolada do retriever e varredura do limiar (SDD §11.2, `make eval-retrieval`).

Sem chamada ao modelo: usa só o embedder local e o índice em disco.
"""

import argparse
import time
from collections.abc import Sequence
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from evals.cases import Case, load_cases
from evals.metrics import (
    ThresholdPoint,
    best_threshold,
    first_hit_rank,
    hit_at,
    mrr,
    percentile,
    threshold_point,
)
from mesa_certa.config import Settings, get_settings
from mesa_certa.domain.date_resolver import SystemClock
from mesa_certa.rag.embedder import Embedder
from mesa_certa.rag.ingest import ingest_directory
from mesa_certa.rag.retriever import Retriever
from mesa_certa.rag.store import ChunkStore

RANK_DEPTH = 5  # hit@5 precisa de 5 posições
SWEEP_RANGE = (0.60, 0.95)
SWEEP_STEP = 0.01


@dataclass(frozen=True)
class RankedCase:
    case: Case
    ranked: list[tuple[str, float]]
    latency_ms: float


@dataclass(frozen=True)
class RetrievalMetrics:
    casos: int
    hit_1: float
    hit_3: float
    hit_5: float
    mrr: float
    latencia_p95_ms: float
    misses: tuple[str, ...]


def rank_cases(retriever: Retriever, cases: Sequence[Case]) -> list[RankedCase]:
    """Ranking bruto (sem limiar) de cada pergunta que envolve a base de conhecimento."""
    relevant = [c for c in cases if c.chunks_esperados or c.is_negative_retrieval]
    if relevant:
        retriever.search(relevant[0].pergunta, RANK_DEPTH)  # aquece o modelo fora da medição
    ranked: list[RankedCase] = []
    for case in relevant:
        started = time.perf_counter()
        chunks = retriever.search(case.pergunta, RANK_DEPTH)
        latency = (time.perf_counter() - started) * 1000
        ranked.append(RankedCase(case, [(c.chunk_id, c.score) for c in chunks], latency))
    return ranked


def retrieval_metrics(ranked: Sequence[RankedCase]) -> RetrievalMetrics:
    positives = [r for r in ranked if r.case.chunks_esperados]
    ranks = [
        first_hit_rank([cid for cid, _ in r.ranked], r.case.chunks_esperados) for r in positives
    ]
    return RetrievalMetrics(
        casos=len(positives),
        hit_1=hit_at(ranks, 1),
        hit_3=hit_at(ranks, 3),
        hit_5=hit_at(ranks, 5),
        mrr=mrr(ranks),
        latencia_p95_ms=percentile([r.latency_ms for r in ranked], 95),
        misses=tuple(
            r.case.id for r, rank in zip(positives, ranks, strict=True) if rank is None or rank > 3
        ),
    )


def sweep(ranked: Sequence[RankedCase], top_k: int) -> list[ThresholdPoint]:
    positives = [(r.ranked, r.case.chunks_esperados) for r in ranked if r.case.chunks_esperados]
    negatives = [r.ranked for r in ranked if r.case.is_negative_retrieval]
    start, stop = SWEEP_RANGE
    steps = round((stop - start) / SWEEP_STEP)
    return [
        threshold_point(start + i * SWEEP_STEP, positives, negatives, top_k)
        for i in range(steps + 1)
    ]


def build_retriever(settings: Settings) -> Retriever:
    embedder = Embedder(settings.embedding_model)
    store = ChunkStore(settings.chroma_path, settings.chroma_collection)
    ingest_directory(
        settings.knowledge_path, embedder, store, SystemClock(ZoneInfo(settings.timezone))
    )
    return Retriever(embedder, store, top_k=settings.rag_top_k)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sem-relatorio", action="store_true", help="só imprime, não grava arquivo"
    )
    args = parser.parse_args()

    from evals.report import render_retrieval, write_report

    settings = get_settings()
    ranked = rank_cases(build_retriever(settings), load_cases())
    metrics = retrieval_metrics(ranked)
    points = sweep(ranked, settings.rag_top_k)
    best = best_threshold(points)

    body = render_retrieval(metrics, points, best, ranked, settings.rag_similarity_threshold)
    print(body)
    if not args.sem_relatorio:
        path = write_report(
            "recuperacao", body, {"recuperacao": metrics, "limiar_recomendado": best}
        )
        print(f"\nRelatório gravado em {path}")


if __name__ == "__main__":
    main()
