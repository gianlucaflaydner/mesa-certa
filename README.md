# Mesa Certa

Assistente conversacional de restaurante que responde dúvidas a partir de uma base de conhecimento (RAG) e consulta, cria e cancela reservas por meio de tools transacionais.

## Documentação

- [PRD](docs/PRD.md): requisitos de produto
- [SDD](docs/SDD.md): desenho técnico
- [Fases](docs/FASES.md): plano de execução da v1

## Como rodar

> Provisório. O fluxo completo com Docker entra na F7.

Pré-requisito: [uv](https://docs.astral.sh/uv/). O uv baixa o Python 3.12 se necessário.

```bash
cp .env.example .env     # a chave da API só é exigida a partir da F4
make install             # uv sync --all-groups
make lint
make typecheck
make test
```

Sem `make` (Windows, por exemplo), rode os comandos equivalentes:

```bash
uv sync --all-groups
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests
uv run pytest -m "not e2e"
```
