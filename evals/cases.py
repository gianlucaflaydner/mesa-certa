"""Leitura de evals/dataset.yaml para estruturas tipadas."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "evals" / "dataset.yaml"

# Um termo obrigatório é texto ou lista de sinônimos (basta um).
Term = str | list[str]


@dataclass(frozen=True)
class Case:
    id: str
    categoria: str
    pergunta: str
    contexto_data: datetime
    tools_esperadas: frozenset[str]
    tools_alternativas: tuple[frozenset[str], ...]
    chunks_esperados: tuple[str, ...]
    deve_citar_fonte: bool
    deve_recusar: bool
    termos_obrigatorios: tuple[Term, ...]
    termos_proibidos: tuple[str, ...]
    referencias: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_negative_retrieval(self) -> bool:
        """Pergunta que a base não responde: a busca deveria voltar abaixo do limiar."""
        return self.categoria == "fora_da_base" or self.id in OUT_OF_DOMAIN_IDS


# Adversariais claramente fora do domínio: se o agente buscar, a base não deve "achar" nada.
OUT_OF_DOMAIN_IDS = frozenset({"adv-002", "adv-008"})


def _case(raw: dict[str, Any]) -> Case:
    return Case(
        id=raw["id"],
        categoria=raw["categoria"],
        pergunta=raw["pergunta"],
        contexto_data=datetime.fromisoformat(raw["contexto_data"]),
        tools_esperadas=frozenset(raw["tools_esperadas"]),
        tools_alternativas=tuple(frozenset(alt) for alt in raw.get("tools_alternativas", [])),
        chunks_esperados=tuple(raw["chunks_esperados"]),
        deve_citar_fonte=bool(raw["deve_citar_fonte"]),
        deve_recusar=bool(raw["deve_recusar"]),
        termos_obrigatorios=tuple(raw["termos_obrigatorios"]),
        termos_proibidos=tuple(raw["termos_proibidos"]),
        referencias=tuple(raw.get("referencias", [])),
    )


def load_cases(path: Path = DATASET_PATH) -> list[Case]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [_case(raw) for raw in data]
