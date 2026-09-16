# ADR-005: resolução de datas em código, não no modelo

| Campo | Valor |
|---|---|
| Situação | aceita |
| Data | 2026-09-14 |
| Fases | F1, F3 |

## Contexto

Erro de data é o modo de falha mais provável e mais danoso do sistema (risco R-03 do PRD): uma reserva no sábado errado é pior do que uma recusa.

## Decisão

O agente recebe data, hora e dia da semana atuais no system prompt e converte expressões como "sábado" para ISO. As tools aceitam somente `YYYY-MM-DD` e `HH:MM` em slots de 30 minutos. Toda normalização, aritmética e validação de janela acontece em `date_resolver.py`, e o relógio é lido em um único ponto do sistema.

## Razão

Cálculo de calendário é determinístico e pertence ao código. Deixar a conta com o modelo troca um resultado garantido por um provável.

## Consequência

As tools rejeitam formato não ISO com erro estruturado (`FORMATO_DATA_INVALIDO`, `FORMATO_HORARIO_INVALIDO`), o que transforma um erro de interpretação em falha explícita dentro do próprio loop, e não em silêncio.

Ler o relógio em um ponto só trouxe um ganho que não era o objetivo inicial: o `Clock` injetável permite fixar o tempo com `FIXED_NOW`, o que torna a demonstração estável e a suite de avaliação reproduzível, já que o seed é ancorado em 2026-09-15.
