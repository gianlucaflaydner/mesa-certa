"""enviar_cardapio (SDD §7.8): entrega o cardápio completo em PDF como anexo da conversa."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from mesa_certa.domain.errors import MenuFileUnavailable
from mesa_certa.tools.base import Tool

NAME = "enviar_cardapio"
DESCRIPTION = (
    "Envia ao cliente o cardápio completo do restaurante em PDF, para abrir ou baixar. Use "
    "quando o cliente pedir o cardápio, o menu, o PDF ou quiser ver todos os pratos e preços. "
    "Para perguntas sobre um prato, ingrediente ou alérgeno específico, use buscar_conhecimento."
)

# Caminho público servido pela API (api/routes.py). O front prefixa com o endereço da API.
MENU_PDF_URL = "/arquivos/cardapio.pdf"
MENU_PDF_DOWNLOAD_NAME = "cardapio-mesa-certa.pdf"


class EnviarCardapioInput(BaseModel):
    model_config = ConfigDict(extra="ignore")


def enviar_cardapio_tool(pdf_path: Path) -> Tool[EnviarCardapioInput]:
    def handle(_: EnviarCardapioInput) -> dict[str, Any]:
        if not pdf_path.is_file():
            raise MenuFileUnavailable(details={"telefone": "(51) 3030-4050"})
        return {
            "tipo": "cardapio_pdf",
            "titulo": "Cardápio Mesa Certa",
            "arquivo": MENU_PDF_DOWNLOAD_NAME,
            "url": MENU_PDF_URL,
            "tamanho_kb": round(pdf_path.stat().st_size / 1024),
            "mensagem": "O arquivo aparece para o cliente abrir ou baixar logo abaixo da resposta.",
        }

    return Tool(NAME, DESCRIPTION, EnviarCardapioInput, handle)
