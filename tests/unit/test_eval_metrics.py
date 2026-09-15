from datetime import datetime

import pytest

from evals.cases import Case, load_cases
from evals.metrics import (
    Outcome,
    ThresholdPoint,
    affirms_term,
    agent_metrics,
    best_threshold,
    cites_source,
    first_hit_rank,
    has_term,
    hit_at,
    judge,
    mrr,
    pass_rate_by_category,
    percentile,
    signals_refusal,
    threshold_point,
)


def _case(**changes: object) -> Case:
    base: dict[str, object] = {
        "id": "rag-900",
        "categoria": "rag_cardapio",
        "pergunta": "O risoto tem lactose?",
        "contexto_data": datetime.fromisoformat("2026-09-15T14:00:00-03:00"),
        "tools_esperadas": frozenset({"buscar_conhecimento"}),
        "tools_alternativas": (),
        "chunks_esperados": ("cardapio.md#pratos-principais>risotos#0",),
        "deve_citar_fonte": True,
        "deve_recusar": False,
        "termos_obrigatorios": ("lactose",),
        "termos_proibidos": ("não contém lactose",),
    }
    base.update(changes)
    return Case(**base)  # type: ignore[arg-type]


def test_dataset_carrega_os_43_casos() -> None:
    cases = load_cases()
    assert len(cases) == 43
    assert sum(c.is_negative_retrieval for c in cases) == 5


def test_termos_ignoram_caixa_acento_e_aceitam_sinonimos() -> None:
    assert has_term("Contém LACTOSE", "lactose")
    assert has_term("até quatro horas antes", ["4 horas", "Quatro horas"])
    assert not has_term("sem restrição", "glúten")


def test_termo_proibido_negado_nao_conta() -> None:
    assert not affirms_term("Não há previsão de reembolso em dobro.", "reembolso em dobro")
    assert affirms_term("Agora você tem reembolso em dobro.", "reembolso em dobro")
    assert affirms_term("Não é isso. O reembolso em dobro vale hoje.", "reembolso em dobro")


def test_marcacao_de_fonte() -> None:
    assert cites_source("Leva queijo.\n\nFonte: cardapio.md › Pratos principais › Risotos")
    assert cites_source("**Fontes:** faq.md")
    assert not cites_source("A fonte de calor é a brasa.")


def test_sinal_de_recusa() -> None:
    assert signals_refusal("Não possuo essa informação. Ligue (51) 3030-4050.")
    assert not signals_refusal("Temos feijoada aos sábados.")


def test_metricas_de_ranking() -> None:
    ranks = [first_hit_rank(["a", "b", "c"], ["b"]), first_hit_rank(["x"], ["b"]), 1]
    assert ranks == [2, None, 1]
    assert hit_at(ranks, 1) == pytest.approx(1 / 3)
    assert hit_at(ranks, 3) == pytest.approx(2 / 3)
    assert mrr(ranks) == pytest.approx((0.5 + 1) / 3)
    assert percentile([10, 20, 30, 40], 95) == 40


def test_limiar_simulado_e_melhor_ponto_no_meio_do_plato() -> None:
    positives = [([("a", 0.9), ("b", 0.8)], ["a"]), ([("c", 0.83)], ["c"])]
    negatives = [[("z", 0.82)]]

    low = threshold_point(0.80, positives, negatives, top_k=4)
    assert (low.recall, low.false_positive_rate) == (1.0, 1.0)
    mid = threshold_point(0.83, positives, negatives, top_k=4)
    assert (mid.recall, mid.false_positive_rate) == (1.0, 0.0)

    points = [
        ThresholdPoint(0.82, 1.0, 1.0),
        ThresholdPoint(0.83, 1.0, 0.0),
        ThresholdPoint(0.84, 1.0, 0.0),
        ThresholdPoint(0.85, 1.0, 0.0),
        ThresholdPoint(0.86, 0.5, 0.0),
    ]
    assert best_threshold(points).threshold == 0.84


def test_julgamento_de_caso_aprovado() -> None:
    outcome = Outcome(
        case_id="rag-900",
        repetition=1,
        reply="Contém lactose.\n\nFonte: cardapio.md › Risotos",
        tools=["buscar_conhecimento"],
    )

    verdict = judge(_case(), outcome)

    assert verdict.passed
    assert verdict.cited is True


def test_julgamento_aponta_cada_motivo() -> None:
    outcome = Outcome(
        case_id="rag-900",
        repetition=1,
        reply="O risoto não contém lactose.",
        tools=["consultar_disponibilidade"],
        exhausted=True,
    )

    verdict = judge(_case(), outcome)

    assert not verdict.routing_ok
    assert verdict.forbidden_hits == ("não contém lactose",)
    assert verdict.cited is False
    assert len(verdict.reasons) == 4


def test_recusa_fora_da_base_exige_sinal() -> None:
    case = _case(
        id="neg-900",
        categoria="fora_da_base",
        chunks_esperados=(),
        deve_citar_fonte=False,
        deve_recusar=True,
        termos_obrigatorios=(),
        termos_proibidos=(),
    )
    ok = Outcome(
        case_id="neg-900",
        repetition=1,
        reply="Não temos essa informação.",
        tools=["buscar_conhecimento"],
    )
    bad = Outcome(
        case_id="neg-900", repetition=1, reply="Sim, temos.", tools=["buscar_conhecimento"]
    )

    assert judge(case, ok).refused is True
    assert judge(case, bad).refused is False


def test_alternativa_de_tools_conta_como_roteamento_certo() -> None:
    case = _case(tools_alternativas=(frozenset(),), termos_obrigatorios=(), deve_citar_fonte=False)

    assert judge(case, Outcome(case_id="rag-900", repetition=1, reply="ok", tools=[])).routing_ok


def test_agregado_da_suite() -> None:
    cases = [
        _case(),
        _case(
            id="adv-900", categoria="adversarial", deve_citar_fonte=False, termos_obrigatorios=()
        ),
    ]
    outcomes = [
        Outcome(
            case_id="rag-900",
            repetition=1,
            reply="lactose. Fonte: cardapio.md",
            tools=["buscar_conhecimento"],
            latency_ms=3000,
            input_tokens=100,
            output_tokens=10,
        ),
        Outcome(
            case_id="adv-900",
            repetition=1,
            reply="Não posso.",
            tools=["buscar_conhecimento"],
            guard_violations=["CONFIRMACAO_SEM_TOOL"],
            latency_ms=5000,
            input_tokens=50,
            output_tokens=5,
        ),
    ]

    metrics = agent_metrics(cases, outcomes)

    assert metrics.acuracia_roteamento == 1.0
    assert metrics.taxa_citacao == 1.0
    assert metrics.taxa_resistencia_injecao == 1.0
    assert metrics.confirmacoes_sem_tool == 1
    assert metrics.tokens_entrada == 150
    assert metrics.latencia_p95_ms == 5000
    assert pass_rate_by_category(cases, outcomes) == {"adversarial": 1.0, "rag_cardapio": 1.0}
