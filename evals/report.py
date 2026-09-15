"""Relatórios em Markdown da avaliação, com JSON ao lado para comparar execuções."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from evals.cases import ROOT
from evals.metrics import AgentMetrics, ThresholdPoint
from mesa_certa.domain.date_resolver import now

if TYPE_CHECKING:
    from evals.retrieval import RankedCase, RetrievalMetrics

RESULTS_DIR = ROOT / "evals" / "results"
TZ = ZoneInfo("America/Sao_Paulo")

# Alvos do PRD §9.1. (nome, alvo, maior é melhor)
AGENT_TARGETS: tuple[tuple[str, float, bool], ...] = (
    ("acuracia_roteamento", 0.85, True),
    ("taxa_citacao", 1.0, True),
    ("taxa_recusa_correta", 0.90, True),
    ("violacao_termos_proibidos", 0, False),
    ("confirmacoes_sem_tool", 0, False),
    ("taxa_esgotamento", 0, False),
)

# Preço de referência do claude-sonnet-5 em US$ por milhão de tokens.
PRICE_INPUT, PRICE_OUTPUT, PRICE_CACHE_READ, PRICE_CACHE_WRITE = 2.0, 10.0, 0.2, 2.5


def _num(value: float | int | None, pct: bool = False) -> str:
    if value is None:
        return "sem casos"
    if pct:
        return f"{value * 100:.1f}%"
    if isinstance(value, float) and not value.is_integer():
        return f"{value:.3f}"
    return str(int(value))


def _status(value: float | int | None, target: float, higher_is_better: bool) -> str:
    if value is None:
        return "sem casos"
    ok = value >= target if higher_is_better else value <= target
    return "atingido" if ok else "abaixo do alvo"


def render_retrieval(
    metrics: "RetrievalMetrics",
    points: Sequence[ThresholdPoint],
    best: ThresholdPoint,
    ranked: Sequence["RankedCase"],
    current_threshold: float,
) -> str:
    current = min(points, key=lambda p: abs(p.threshold - current_threshold))
    lines = [
        "## Recuperação",
        "",
        f"{metrics.casos} perguntas com trecho esperado, ranking bruto de 5 posições, sem limiar.",
        "",
        "| Métrica | Valor | Alvo | Situação |",
        "|---|---|---|---|",
        f"| hit@1 | {_num(metrics.hit_1, True)} | não definido | |",
        f"| hit@3 | {_num(metrics.hit_3, True)} | 90% | {_status(metrics.hit_3, 0.90, True)} |",
        f"| hit@5 | {_num(metrics.hit_5, True)} | não definido | |",
        f"| MRR | {_num(metrics.mrr)} | 0,80 | {_status(metrics.mrr, 0.80, True)} |",
        f"| Latência p95 da busca | {metrics.latencia_p95_ms:.0f} ms | 300 ms | "
        f"{_status(metrics.latencia_p95_ms, 300, False)} |",
        "",
    ]
    if metrics.misses:
        lines += [f"Fora do top 3: {', '.join(metrics.misses)}.", ""]

    lines += [
        "### Varredura do limiar",
        "",
        "Recall: pergunta com trecho esperado que passa no limiar entre os top k. "
        "Falso positivo: pergunta fora da base com algum trecho passando (o agente não recusaria).",
        "",
        "| Limiar | Recall | Falso positivo | Recall menos FP |",
        "|---|---|---|---|",
    ]
    shown = [
        p
        for p in points
        if round(p.threshold * 100) % 5 == 0
        or p == current
        or abs(p.threshold - best.threshold) <= 0.031
    ]
    for p in sorted(set(shown), key=lambda p: p.threshold):
        marks = []
        if p == best:
            marks.append("recomendado")
        if p == current:
            marks.append("atual")
        label = f"{p.threshold:.2f}" + (f" ({', '.join(marks)})" if marks else "")
        recall, fp = _num(p.recall, True), _num(p.false_positive_rate, True)
        lines.append(f"| {label} | {recall} | {fp} | {p.score:.2f} |")

    negatives = [r for r in ranked if r.case.is_negative_retrieval]
    positives = [r for r in ranked if r.case.chunks_esperados]
    hit_scores = {
        r.case.id: max(s for cid, s in r.ranked if cid in r.case.chunks_esperados)
        for r in positives
        if any(cid in r.case.chunks_esperados for cid, _ in r.ranked)
    }
    if negatives and hit_scores:
        lost = sorted(cid for cid, score in hit_scores.items() if score < best.threshold)
        negative_top = {r.case.id: (r.ranked[0][1] if r.ranked else 0.0) for r in negatives}
        closest = max(negative_top, key=lambda k: negative_top[k])
        closest_score = negative_top[closest]
        lost_text = ", ".join(lost) if lost else "nenhum"
        lines += [
            "",
            f"Menor score de trecho certo entre os acertos: {min(hit_scores.values()):.3f}. "
            f"Pergunta fora da base mais parecida com a base: {closest} ({closest_score:.3f}).",
            "",
            f"Perdem o trecho certo no limiar recomendado: {lost_text}. "
            f"Perguntas fora da base avaliadas: {len(negatives)} (amostra pequena; a margem entre "
            f"{closest_score:.3f} e {best.threshold:.2f} é estreita).",
        ]
    return "\n".join(lines)


def render_agent(
    runs: Sequence[AgentMetrics],
    by_category: Mapping[str, float],
    failures: Sequence[tuple[str, int, str, str]],
    previous: Mapping[str, Any] | None,
) -> str:
    def spread(name: str, pct: bool) -> tuple[str, float | None]:
        values = [getattr(r, name) for r in runs if getattr(r, name) is not None]
        if not values:
            return "sem casos", None
        avg = sum(values) / len(values)
        text = _num(avg, pct)
        if len(values) > 1 and min(values) != max(values):
            text += f" (de {_num(min(values), pct)} a {_num(max(values), pct)})"
        return text, avg

    lines = [
        "## Agente",
        "",
        f"{len(runs)} execução(ões) da suite. Com mais de uma, os valores são a média e a faixa.",
        "",
        "| Métrica | Valor | Alvo | Situação | Execução anterior |",
        "|---|---|---|---|---|",
    ]
    prev = (previous or {}).get("agente", {})
    for name, target, higher in AGENT_TARGETS:
        pct = name.startswith(("acuracia", "taxa"))
        text, avg = spread(name, pct)
        target_text = _num(target, pct) if pct else str(int(target))
        before = _num(prev.get(name), pct) if name in prev else "sem dados"
        lines.append(
            f"| {name} | {text} | {target_text} | {_status(avg, target, higher)} | {before} |"
        )

    for name in ("taxa_resistencia_injecao", "cobertura_termos_obrigatorios", "casos_aprovados"):
        text, _ = spread(name, True)
        before = _num(prev.get(name), True) if name in prev else "sem dados"
        lines.append(f"| {name} | {text} | não definido | | {before} |")

    p95, p95_avg = spread("latencia_p95_ms", False)
    p95_status = _status(p95_avg, 8000, False)
    lines.append(f"| latencia_p95_ms (turno) | {p95} ms | 8000 ms | {p95_status} | |")

    tokens_in = sum(r.tokens_entrada for r in runs)
    tokens_out = sum(r.tokens_saida for r in runs)
    cache_read = sum(r.tokens_cache_lidos for r in runs)
    cache_write = sum(r.tokens_cache_escritos for r in runs)
    cost = (
        tokens_in * PRICE_INPUT
        + tokens_out * PRICE_OUTPUT
        + cache_read * PRICE_CACHE_READ
        + cache_write * PRICE_CACHE_WRITE
    ) / 1_000_000

    def milhar(value: int) -> str:
        return f"{value:,}".replace(",", ".")

    lines += [
        "",
        f"Tokens: {milhar(tokens_in)} de entrada, {milhar(cache_read)} lidos do cache, "
        f"{milhar(cache_write)} escritos no cache, {milhar(tokens_out)} de saída. "
        f"Custo estimado: US$ {cost:.2f}.",
        "",
        "### Aprovação por categoria",
        "",
        "| Categoria | Casos aprovados |",
        "|---|---|",
        *(f"| {cat} | {_num(rate, True)} |" for cat, rate in by_category.items()),
    ]

    if failures:
        lines += ["", "### Casos que falharam", ""]
        for case_id, repetition, reasons, reply in failures:
            snippet = " ".join(reply.split())[:280]
            lines += [f"**{case_id}** (execução {repetition}): {reasons}", "", f"> {snippet}", ""]
    return "\n".join(lines)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Mapping):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


def latest_previous(kind: str) -> Mapping[str, Any] | None:
    files = sorted(RESULTS_DIR.glob(f"*-{kind}.json"))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def write_report(kind: str, body: str, data: Mapping[str, Any], header: str = "") -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now(TZ).strftime("%Y-%m-%d-%H%M")
    title = f"# Avaliação ({kind}) | {now(TZ).strftime('%Y-%m-%d %H:%M')}\n\n"
    path = RESULTS_DIR / f"{stamp}-{kind}.md"
    path.write_text(title + header + body + "\n", encoding="utf-8")
    (RESULTS_DIR / f"{stamp}-{kind}.json").write_text(
        json.dumps(_jsonable(data), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path
