"""Configuração da aplicação.

Único ponto do projeto que lê variáveis de ambiente (SDD §12).
"""

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
Effort = Literal["low", "medium", "high", "xhigh", "max"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # `CHAVE=` vazio no .env vale como não definido (ex.: FIXED_NOW e ANTHROPIC_API_KEY).
        env_parse_none_str="",
        # Campos model_* colidem com o namespace protegido padrão do Pydantic.
        protected_namespaces=("settings_",),
    )

    # Modelo
    anthropic_api_key: SecretStr | None = None
    # Obrigatório quando a chave não pertence a um workspace (vai no header anthropic-workspace-id).
    anthropic_workspace_id: str | None = None
    model_name: str = "claude-sonnet-5"
    # Os modelos atuais não aceitam temperature; a profundidade é regulada por effort.
    model_effort: Effort = "medium"
    # O thinking adaptativo consome do mesmo limite: valores baixos truncam a resposta.
    model_max_tokens: int = Field(default=16000, gt=0)

    # RAG
    embedding_model: str = "intfloat/multilingual-e5-small"
    chroma_path: Path = Path("./data/chroma")
    chroma_collection: str = "mesa_certa_kb"
    knowledge_path: Path = Path("./data/knowledge")
    rag_top_k: int = Field(default=4, gt=0)
    rag_similarity_threshold: float = Field(default=0.72, ge=0.0, le=1.0)
    rag_max_context_chars: int = Field(default=4000, gt=0)

    # Banco
    database_url: str = "sqlite:///./data/mesa_certa.db"

    # Agente
    agent_max_iterations: int = Field(default=8, gt=0)
    session_ttl_minutes: int = Field(default=60, gt=0)
    session_max_messages: int = Field(default=20, gt=0)

    # Aplicação
    timezone: str = "America/Sao_Paulo"
    log_level: LogLevel = "INFO"
    trace_path: Path = Path("./data/traces")
    debug_ui: bool = False
    # Relógio fixo para demo e avaliação: o seed é ancorado em 2026-09-15.
    fixed_now: datetime | None = None
    # Origens do front-end autorizadas a chamar a API (CORS).
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
