# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Estágio 1: construção. Tem uv, compilador e cache; nada disso vai para a imagem final.
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_PREFERENCE=only-system \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    HF_HOME=/opt/huggingface

WORKDIR /app

# Só as dependências: camada reaproveitada enquanto pyproject e uv.lock não mudarem.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Modelo de embedding baixado no build, não no primeiro pedido do usuário.
RUN /app/.venv/bin/python -c \
    "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"

# O projeto em si, instalado por último.
COPY src ./src
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Estágio 2: execução. Python puro, sem uv e sem cache de build.
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/huggingface \
    HF_HUB_OFFLINE=1 \
    PATH="/app/.venv/bin:$PATH"

# Usuário comum criado antes de qualquer cópia: assim nenhuma camada precisa de chown depois.
RUN useradd --create-home --uid 1000 app && mkdir -p /app/var && chown -R app:app /app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /opt/huggingface /opt/huggingface
COPY --chown=app:app src ./src
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app data/knowledge ./data/knowledge
COPY --chown=app:app docs ./docs
COPY --chown=app:app --chmod=755 docker/entrypoint.sh ./docker/entrypoint.sh

USER app

EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["uvicorn", "mesa_certa.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
