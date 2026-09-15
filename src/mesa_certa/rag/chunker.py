"""Chunking estrutural de Markdown (SDD §6.2).

Regras:
- preâmbulo antes do primeiro `##` não vira chunk;
- cada seção mais profunda (`###`, senão `##`) é um chunk candidato;
- seção abaixo de 80 caracteres é fundida ao irmão seguinte e herda o id dele;
- seção acima de 1.200 caracteres é dividida por parágrafo, com 1 de sobreposição;
- tabela nunca é partida (é um parágrafo só, pois não tem linha em branco).
"""

import hashlib
import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

MAX_CHARS = 1200
MIN_CHARS = 80
PATH_SEPARATOR = " > "
CITATION_SEPARATOR = " › "

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return _NON_SLUG.sub("-", ascii_text.lower()).strip("-")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source: str
    doc_title: str
    h2: str
    h3: str | None
    content: str

    @property
    def section_path(self) -> str:
        return PATH_SEPARATOR.join(self._headings())

    @property
    def section_label(self) -> str:
        return CITATION_SEPARATOR.join(self._headings())

    @property
    def text(self) -> str:
        """Texto enviado ao embedding: caminho hierárquico e conteúdo."""
        return f"{self.doc_title}{PATH_SEPARATOR}{self.section_path}\n\n{self.content}"

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    @property
    def char_count(self) -> int:
        return len(self.content)

    def _headings(self) -> list[str]:
        return [self.h2] if self.h3 is None else [self.h2, self.h3]


@dataclass(frozen=True)
class _Section:
    h2: str
    h3: str | None
    body: str

    @property
    def heading(self) -> str:
        return self.h3 if self.h3 is not None else self.h2

    def is_sibling_of(self, other: "_Section") -> bool:
        if self.h3 is None or other.h3 is None:
            return self.h3 is None and other.h3 is None
        return self.h2 == other.h2


def chunk_document(source: str, markdown: str) -> list[Chunk]:
    title, sections = _parse(source, markdown)
    chunks: list[Chunk] = []
    for section in _merge_small(sections):
        base_id = f"{source}#{slug(section.h2)}"
        if section.h3 is not None:
            base_id += f">{slug(section.h3)}"
        for index, part in enumerate(_split(section.body)):
            chunks.append(Chunk(f"{base_id}#{index}", source, title, section.h2, section.h3, part))

    ids = [c.chunk_id for c in chunks]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"chunk_id duplicado em {source}: {', '.join(duplicates)}")
    return chunks


def chunk_directory(path: Path) -> list[Chunk]:
    return [
        chunk
        for file in sorted(path.glob("*.md"))
        for chunk in chunk_document(file.name, file.read_text(encoding="utf-8"))
    ]


def _parse(source: str, markdown: str) -> tuple[str, list[_Section]]:
    title: str | None = None
    h2: str | None = None
    h3: str | None = None
    lines: list[str] = []
    sections: list[_Section] = []

    def close() -> None:
        body = "\n".join(lines).strip()
        if h2 is not None and body:
            sections.append(_Section(h2, h3, body))
        lines.clear()

    for line in _outside_fences(markdown.splitlines()):
        if line.startswith("# ") and title is None:
            title = line[2:].strip()
        elif line.startswith("## "):
            close()
            h2, h3 = line[3:].strip(), None
        elif line.startswith("### ") and h2 is not None:
            close()
            h3 = line[4:].strip()
        else:
            lines.append(line)
    close()

    if title is None:
        raise ValueError(f"{source} não começa com '# Título'")
    return title, sections


def _outside_fences(lines: list[str]) -> Iterator[str]:
    """Troca linhas de cabeçalho dentro de blocos de código por texto neutro."""
    in_fence = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        yield f" {line}" if in_fence and line.startswith("#") else line


def _merge_small(sections: list[_Section]) -> list[_Section]:
    merged: list[_Section] = []
    carry = ""
    for index, section in enumerate(sections):
        body = f"{carry}\n\n{section.body}" if carry else section.body
        following = sections[index + 1] if index + 1 < len(sections) else None
        if len(body) < MIN_CHARS and following is not None and following.is_sibling_of(section):
            carry = f"{carry}\n\n{section.heading}\n\n{section.body}".strip()
            continue
        merged.append(_Section(section.h2, section.h3, body))
        carry = ""
    return merged


def _split(body: str) -> list[str]:
    if len(body) <= MAX_CHARS:
        return [body]

    parts: list[list[str]] = []
    current: list[str] = []
    fresh = 0  # parágrafos da parte atual que não vieram da sobreposição
    for paragraph in (p.strip() for p in _PARAGRAPH_BREAK.split(body) if p.strip()):
        if fresh and len("\n\n".join([*current, paragraph])) > MAX_CHARS:
            parts.append(current)
            current = [current[-1]]
            fresh = 0
        current.append(paragraph)
        fresh += 1
    parts.append(current)
    return ["\n\n".join(part) for part in parts]
