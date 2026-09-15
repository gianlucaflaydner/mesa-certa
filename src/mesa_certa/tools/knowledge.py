"""buscar_conhecimento (SDD §7.1)."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from mesa_certa.domain.rules import RESTAURANT_PHONE
from mesa_certa.rag.retriever import Retriever
from mesa_certa.tools.base import Tool

NAME = "buscar_conhecimento"
DESCRIPTION = (
    "Busca informações na base de conhecimento do restaurante: cardápio, ingredientes, "
    "alérgenos, preços de itens fixos, políticas da casa, perguntas frequentes e informações "
    "institucionais. Use SEMPRE que a pergunta for sobre o que o restaurante oferece, do que é "
    "feito um prato, restrições alimentares ou regras da casa. NÃO use para disponibilidade de "
    "mesas, reservas específicas ou prato do dia."
)
NO_INFORMATION_MESSAGE = (
    "Nenhum trecho da base atingiu a relevância mínima. Diga que não possui essa informação "
    f"e ofereça o telefone {RESTAURANT_PHONE}."
)


class BuscarConhecimentoInput(BaseModel):
    pergunta: str = Field(
        description=(
            "A pergunta em linguagem natural, reformulada de forma completa e independente "
            "do histórico da conversa."
        )
    )
    top_k: int | None = Field(
        default=None, ge=1, le=8, description="Quantidade de trechos a recuperar. Padrão 4."
    )

    @field_validator("pergunta")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a pergunta não pode ser vazia")
        return value.strip()


def buscar_conhecimento_tool(retriever: Retriever) -> Tool[BuscarConhecimentoInput]:
    def handle(params: BuscarConhecimentoInput) -> dict[str, Any]:
        result = retriever.retrieve(params.pergunta, params.top_k)
        data: dict[str, Any] = {
            "trechos": [
                {
                    "indice": index,
                    "fonte": chunk.source,
                    "secao": chunk.section_label,
                    "citacao": chunk.citation,
                    "chunk_id": chunk.chunk_id,
                    "relevancia": round(chunk.score, 2),
                    "conteudo": chunk.content,
                }
                for index, chunk in enumerate(result.chunks, start=1)
            ],
            "encontrou_informacao": not result.below_threshold,
        }
        if result.below_threshold:
            data["mensagem"] = NO_INFORMATION_MESSAGE
        return data

    return Tool(NAME, DESCRIPTION, BuscarConhecimentoInput, handle)
