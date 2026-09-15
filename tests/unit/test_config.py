from pathlib import Path

import pytest
from pydantic import ValidationError

from mesa_certa.config import Settings, get_settings


@pytest.fixture
def ambiente_limpo(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for campo in Settings.model_fields:
        monkeypatch.delenv(campo.upper(), raising=False)
    return monkeypatch


def test_defaults_sem_env(ambiente_limpo: pytest.MonkeyPatch) -> None:
    s = Settings(_env_file=None)

    assert s.anthropic_api_key is None
    assert s.model_name == "claude-sonnet-5"
    assert s.model_effort == "medium"
    assert s.model_max_tokens == 16000
    assert s.embedding_model == "intfloat/multilingual-e5-small"
    assert s.chroma_path == Path("./data/chroma")
    assert s.chroma_collection == "mesa_certa_kb"
    assert s.knowledge_path == Path("./data/knowledge")
    assert s.rag_top_k == 4
    assert s.rag_similarity_threshold == 0.72
    assert s.rag_max_context_chars == 4000
    assert s.database_url == "sqlite:///./data/mesa_certa.db"
    assert s.agent_max_iterations == 8
    assert s.session_ttl_minutes == 60
    assert s.session_max_messages == 20
    assert s.timezone == "America/Sao_Paulo"
    assert s.log_level == "INFO"
    assert s.trace_path == Path("./data/traces")
    assert s.debug_ui is False


def test_variavel_de_ambiente_sobrescreve(ambiente_limpo: pytest.MonkeyPatch) -> None:
    ambiente_limpo.setenv("ANTHROPIC_API_KEY", "sk-teste")
    ambiente_limpo.setenv("RAG_TOP_K", "7")
    ambiente_limpo.setenv("RAG_SIMILARITY_THRESHOLD", "0.65")
    ambiente_limpo.setenv("DEBUG_UI", "true")
    ambiente_limpo.setenv("TRACE_PATH", "/tmp/traces")

    s = Settings(_env_file=None)

    assert s.anthropic_api_key is not None
    assert s.anthropic_api_key.get_secret_value() == "sk-teste"
    assert s.rag_top_k == 7
    assert s.rag_similarity_threshold == 0.65
    assert s.debug_ui is True
    assert s.trace_path == Path("/tmp/traces")


def test_chave_nao_aparece_no_repr(ambiente_limpo: pytest.MonkeyPatch) -> None:
    ambiente_limpo.setenv("ANTHROPIC_API_KEY", "sk-segredo")

    assert "sk-segredo" not in repr(Settings(_env_file=None))


def test_valor_invalido_e_rejeitado(ambiente_limpo: pytest.MonkeyPatch) -> None:
    ambiente_limpo.setenv("RAG_SIMILARITY_THRESHOLD", "1.5")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_usa_cache(ambiente_limpo: pytest.MonkeyPatch) -> None:
    assert get_settings() is get_settings()


def test_fixture_aponta_para_diretorio_temporario(settings: Settings, tmp_path: Path) -> None:
    assert settings.chroma_path.is_relative_to(tmp_path)
    assert settings.knowledge_path.is_relative_to(tmp_path)
    assert settings.trace_path.is_relative_to(tmp_path)
    assert tmp_path.as_posix() in settings.database_url
