"""Avaliação do agente de ponta a ponta (SDD §11.3, `make eval`).

Para cada caso: banco semeado do zero, relógio parado em `contexto_data`, um turno com a API
real do modelo e o trace do turno. Custa chamadas pagas; use `--casos` para rodar poucos.

    uv run python -m evals.runner                     # suite completa, uma vez
    uv run python -m evals.runner --repeticoes 3      # mede a variação do modelo
    uv run python -m evals.runner --casos rag-001,neg-002 --limiar 0.85
"""

import argparse
import json
import tempfile
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from evals.cases import ROOT, Case, load_cases
from evals.metrics import Outcome, agent_metrics, judge, pass_rate_by_category
from evals.report import RESULTS_DIR, latest_previous, render_agent, write_report
from mesa_certa.agent.factory import build_app, build_llm
from mesa_certa.agent.llm import LLMClient
from mesa_certa.config import Settings, get_settings
from mesa_certa.db.reset import reset_database
from mesa_certa.domain.date_resolver import FixedClock
from mesa_certa.rag.embedder import Embedder, TextEmbedder
from mesa_certa.rag.ingest import ingest_directory
from mesa_certa.rag.store import ChunkStore

MIGRATIONS = ROOT / "migrations"


def run_case(
    case: Case,
    repetition: int,
    settings: Settings,
    llm: LLMClient,
    embedder: TextEmbedder,
    store: ChunkStore,
    workdir: Path,
) -> Outcome:
    """Um turno isolado: banco próprio, relógio próprio, sessão nova."""
    db_path = workdir / f"{case.id}-{repetition}.db"
    case_settings = settings.model_copy(
        update={
            "database_url": f"sqlite:///{db_path.as_posix()}",
            "trace_path": workdir / "traces",
        }
    )
    reset_database(case_settings.database_url, MIGRATIONS)
    app = build_app(case_settings, FixedClock(case.contexto_data), llm, embedder, store)
    outcome = Outcome(case_id=case.id, repetition=repetition)
    try:
        turn = app.agent.run_turn(app.sessions.create(), case.pergunta)
        trace = app.tracer.get(turn.trace_id)
        outcome.reply = turn.reply
        outcome.tools = [t.name for t in turn.tool_calls]
        outcome.citations = [c.chunk_id for c in turn.citations]
        outcome.guard_violations = list(turn.guard_violations)
        outcome.exhausted = turn.exhausted
        outcome.latency_ms = turn.latency_ms
        outcome.input_tokens = turn.usage.input_tokens
        outcome.output_tokens = turn.usage.output_tokens
        outcome.cache_read_tokens = turn.usage.cache_read_input_tokens
        outcome.cache_creation_tokens = turn.usage.cache_creation_input_tokens
        outcome.below_threshold = [r.below_threshold for r in trace.retrievals] if trace else []
    except Exception as exc:  # um caso com erro não derruba a suite
        outcome.error = f"{type(exc).__name__}: {exc}"[:300]
    finally:
        app.close()
    return outcome


def run_suite(cases: Sequence[Case], repetitions: int, settings: Settings) -> list[list[Outcome]]:
    embedder = Embedder(settings.embedding_model)
    store = ChunkStore(settings.chroma_path, settings.chroma_collection)
    ingest_directory(settings.knowledge_path, embedder, store, FixedClock(cases[0].contexto_data))
    # Carrega o modelo de embeddings antes, senão o primeiro turno mede o carregamento.
    embedder.embed_query("aquecimento")
    llm = build_llm(settings)

    runs: list[list[Outcome]] = []
    with tempfile.TemporaryDirectory(prefix="mesa-certa-eval-") as tmp:
        for repetition in range(1, repetitions + 1):
            outcomes: list[Outcome] = []
            for index, case in enumerate(cases, start=1):
                outcome = run_case(case, repetition, settings, llm, embedder, store, Path(tmp))
                verdict = judge(case, outcome)
                status = "ok" if verdict.passed else f"FALHOU: {'; '.join(verdict.reasons)}"
                print(
                    f"[{repetition}/{repetitions}] {index:>2}/{len(cases)} {case.id}: {status}",
                    flush=True,
                )
                outcomes.append(outcome)
            runs.append(outcomes)
    return runs


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repeticoes", type=int, default=1)
    parser.add_argument("--casos", help="ids separados por vírgula")
    parser.add_argument("--categoria", help="só uma categoria do dataset")
    parser.add_argument(
        "--limiar", type=float, help="sobrepõe RAG_SIMILARITY_THRESHOLD nesta execução"
    )
    args = parser.parse_args()

    settings = get_settings()
    if args.limiar is not None:
        settings = settings.model_copy(update={"rag_similarity_threshold": args.limiar})
    if settings.anthropic_api_key is None:
        raise SystemExit("ANTHROPIC_API_KEY não configurada: a avaliação do agente usa a API real.")

    cases = load_cases()
    if args.casos:
        wanted = {c.strip() for c in args.casos.split(",")}
        cases = [c for c in cases if c.id in wanted]
    if args.categoria:
        cases = [c for c in cases if c.categoria == args.categoria]
    if not cases:
        raise SystemExit("Nenhum caso selecionado.")

    runs = run_suite(cases, args.repeticoes, settings)
    per_run = [agent_metrics(cases, outcomes) for outcomes in runs]
    all_outcomes = [o for outcomes in runs for o in outcomes]
    by_id = {c.id: c for c in cases}
    failures = [
        (o.case_id, o.repetition, "; ".join(v.reasons), o.reply)
        for o in all_outcomes
        if not (v := judge(by_id[o.case_id], o)).passed
    ]

    partial = len(cases) < len(load_cases())
    kind = "agente-parcial" if partial else "agente"
    header = (
        f"Modelo `{settings.model_name}`, effort `{settings.model_effort}`, limiar "
        f"{settings.rag_similarity_threshold:.2f}, {len(cases)} casos, "
        f"{args.repeticoes} repetição(ões).\n\n"
    )
    body = render_agent(
        per_run, pass_rate_by_category(cases, all_outcomes), failures, latest_previous(kind)
    )
    mean_metrics = {
        name: sum(getattr(m, name) or 0 for m in per_run) / len(per_run)
        for name in asdict(per_run[0])
    }
    path = write_report(kind, body, {"agente": mean_metrics, "execucoes": per_run}, header)

    raw = RESULTS_DIR / "raw" / f"{path.stem}.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(
        "\n".join(json.dumps(asdict(o), ensure_ascii=False) for o in all_outcomes), encoding="utf-8"
    )
    print(f"\n{header}{body}\n\nRelatório: {path}\nRespostas brutas: {raw}")


if __name__ == "__main__":
    main()
