# ADR-002: recuperação como tool (agentic RAG)

| Campo | Valor |
|---|---|
| Situação | aceita |
| Data | 2026-09-14 |
| Fases | F2, F3, F6 |

## Contexto

O pipeline clássico de RAG recupera antes de toda geração, sem consultar o modelo.

## Decisão

Expor a recuperação como a tool `buscar_conhecimento`, que o modelo decide quando chamar.

## Razão

Nem todo turno precisa de recuperação. "Quero cancelar a reserva K7M2QP" não precisa. Recuperar sempre injeta ruído no contexto e gasta tokens. Como tool, a decisão de recuperar fica visível no trace e vira métrica: acurácia de roteamento.

## Consequência

O modelo pode deixar de chamar a tool quando deveria. Isso é mitigado por instrução explícita no system prompt e por casos dedicados no dataset de avaliação.

A última rodada da F6 mediu acurácia de roteamento de 100% em 43 casos e 3 repetições, contra alvo de 85%. O risco existe, mas é medido a cada execução da suite, e não presumido.
