"""Busca manual na base: imprime id, score e trecho de cada resultado.

Uso: python scripts/search.py "opções sem glúten" [--k 5]
"""

import argparse
import textwrap

from mesa_certa.config import get_settings
from mesa_certa.rag.embedder import Embedder
from mesa_certa.rag.retriever import Retriever
from mesa_certa.rag.store import ChunkStore

SNIPPET_CHARS = 160


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--k", type=int, default=settings.rag_top_k)
    args = parser.parse_args()

    retriever = Retriever(
        Embedder(settings.embedding_model),
        ChunkStore(settings.chroma_path, settings.chroma_collection),
        top_k=args.k,
        similarity_threshold=settings.rag_similarity_threshold,
        max_context_chars=settings.rag_max_context_chars,
    )
    results = retriever.search(args.query)
    if not results:
        print("Índice vazio. Rode `make ingest` antes.")
        return

    for rank, chunk in enumerate(results, start=1):
        marker = "" if chunk.score >= retriever.similarity_threshold else "  (abaixo do limiar)"
        snippet = textwrap.shorten(chunk.content, SNIPPET_CHARS, placeholder="...")
        print(f"{rank}. {chunk.score:.3f}  {chunk.chunk_id}{marker}\n   {snippet}")


if __name__ == "__main__":
    main()
