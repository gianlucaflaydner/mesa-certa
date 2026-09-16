# ADR-004: SQLite e ChromaDB em disco

| Campo | Valor |
|---|---|
| Situação | aceita |
| Data | 2026-09-14 |
| Fases | F1, F2, F7 |

## Contexto

O RNF-06 exige que o sistema suba com um comando. Bancos em serviço separado custam operação e configuração.

## Decisão

SQLite para o estado transacional e ChromaDB em disco para o índice vetorial, ambos como arquivos, sem contêiner de banco.

## Razão

Postgres com pgvector seria a escolha de produção, mas para a escala do projeto adiciona operação sem ganho demonstrável.

## Consequência

Escrita concorrente é limitada, o que é aceitável porque a v1 não tem carga concorrente real. A camada de repositório isola o SQLAlchemy o suficiente para uma troca futura.

Duas consequências práticas na implementação:

1. A criação de reserva precisa de `BEGIN IMMEDIATE` para que duas tentativas simultâneas na última mesa não vençam as duas. Há teste com duas threads que prova que apenas uma vence.
2. Em Docker, os dois arquivos vivem num volume montado em `/app/var`, separado da base de conhecimento, que fica dentro da imagem. Manter os dois na mesma pasta faria o volume congelar uma cópia dos documentos e a ingestão deixaria de ver edições.
