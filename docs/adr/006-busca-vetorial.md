# ADR-006: busca puramente vetorial na v1

| Campo | Valor |
|---|---|
| Situação | aceita, com ressalva medida |
| Data | 2026-09-14 |
| Fases | F2, F6 |

## Contexto

Busca híbrida (vetorial com BM25) e reranker melhoram recuperação, ao custo de mais peças e mais latência.

## Decisão

Somente busca vetorial na v1, sem BM25 e sem reranker.

## Razão

Estabelecer uma linha de base mensurável antes de otimizar. A busca híbrida entra na v2 comparada numericamente contra esta linha de base, o que é um argumento melhor de portfólio do que já começar complexo.

## Consequência

A linha de base ficou registrada em `evals/results/`: hit@3 de 94,1% (alvo 90%) e MRR de 0,755 (alvo 0,80, abaixo do alvo). O MRR mostra o limite da abordagem, porque o trecho certo costuma vir no top 3, mas nem sempre em primeiro.

A varredura do limiar expôs a consequência mais séria. Como o E5 concentra os scores numa faixa estreita, a separação entre pergunta coberta pela base e pergunta fora dela é apertada: o menor score de acerto é 0,827 e a pergunta fora da base mais parecida marca 0,837. O limiar foi fixado em 0,85, que zera o falso positivo com recall de 88,2%, mas a margem é pequena e a amostra de negativos também (5 perguntas). Um reranker resolveria essa separação melhor do que qualquer ajuste de limiar, e é a primeira candidata da v2.
