"""Configuração da aplicação.

Único ponto do projeto que lê variáveis de ambiente (SDD §12).
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Campos model_* colidem com o namespace protegido padrão do Pydantic.
        protected_namespaces=("settings_",),
    )

    # Modelo
    anthropic_api_key: SecretStr | None = None
    model_name: str = "claude-sonnet-5"
    model_temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    model_max_tokens: int = Field(default=2048, gt=0)

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
