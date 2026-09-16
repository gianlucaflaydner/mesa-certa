# ADR-001: loop de tool calling próprio em vez de framework

| Campo | Valor |
|---|---|
| Situação | aceita |
| Data | 2026-09-14 |
| Fases | F4 |

## Contexto

LangChain e LangGraph resolveriam a orquestração do agente com menos código. O projeto é de portfólio e precisa demonstrar domínio do mecanismo de tool calling, não apenas o uso de uma abstração pronta.

## Decisão

Implementar o loop manualmente sobre o SDK da Anthropic, em `agent/loop.py`, com cliente LLM injetável.

## Razão

O loop é o núcleo conceitual do projeto. Um framework esconderia justamente o que se quer mostrar, traria dependência pesada e dificultaria o trace granular exigido pelo RF-13.

## Consequência

Retry, limite de iteração, tools em paralelo na mesma resposta e serialização de erro passam a ser responsabilidade do projeto, cada um com teste próprio.

Na prática, o loop ficou em cerca de 120 linhas e é coberto por testes de integração com cliente falso roteirizado: turno sem tool, com uma tool, com duas tools na mesma resposta, erro de tool e estouro de iterações. O trace por turno saiu de graça, porque o loop é nosso.
