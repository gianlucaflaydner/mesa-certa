# ADR-003: embeddings locais em CPU

| Campo | Valor |
|---|---|
| Situação | aceita |
| Data | 2026-09-14 |
| Fases | F2, F6, F7 |

## Contexto

A base de conhecimento é reindexada a cada alteração dos documentos. Um serviço externo de embeddings cobraria por reindexação e exigiria rede.

## Decisão

Usar `intfloat/multilingual-e5-small` via `sentence-transformers`, em CPU, com o modelo embutido na imagem Docker.

## Razão

Custo zero por reindexação (RNF-07), funciona offline e a base tem poucos milhares de chunks, escala em que a CPU basta. O modelo tem bom desempenho em português e apenas 384 dimensões, o que mantém o índice leve.

## Consequência

O E5 exige prefixos assimétricos: `query: ` nas consultas e `passage: ` nos documentos. Omitir o prefixo degrada a recuperação em silêncio, sem erro. O `Embedder` encapsula isso e há teste que garante o comportamento.

Duas consequências apareceram depois:

1. O modelo concentra os scores numa faixa alta e estreita, o que tornou a calibração do limiar mais delicada do que o esperado (ver [ADR-006](006-busca-vetorial.md) e a decisão D5 em [FASES.md](../FASES.md)).
2. Baixar o modelo no build deixa a imagem da API em cerca de 3,2 GB, contra 412 MB da imagem do front. Foi troca consciente: espaço em disco em troca de partida previsível, sem download no primeiro pedido do usuário.
