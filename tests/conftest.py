from pathlib import Path

import pytest

from mesa_certa.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _limpa_cache_settings() -> None:
    get_settings.cache_clear()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings isoladas do .env local, com todo I/O em diretório temporário."""
    return Settings(
        _env_file=None,
        chroma_path=tmp_path / "chroma",
        knowledge_path=tmp_path / "knowledge",
        database_url=f"sqlite:///{(tmp_path / 'mesa_certa.db').as_posix()}",
        trace_path=tmp_path / "traces",
    )
