"""Small BM25 index over the Markdown knowledge corpus, split into one chunk per section."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

K1 = 1.5
B = 0.75
_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class Chunk:
    doc_id: str
    heading: str
    text: str


class KnowledgeIndex:
    """BM25 over sections: plain, dependency-free and deterministic, which suits a baseline."""

    def __init__(self, directory: Path) -> None:
        self.documents: dict[str, str] = {}
        self.chunks: list[Chunk] = []
        for path in sorted(directory.glob("*.md")):
            text = path.read_text()
            self.documents[path.stem] = text
            self.chunks.extend(_split(path.stem, text))
        self._tokens = [_tokenize(f"{c.doc_id} {c.heading} {c.text}") for c in self.chunks]
        self._average = sum(map(len, self._tokens)) / max(len(self._tokens), 1)
        frequency = Counter(term for tokens in self._tokens for term in set(tokens))
        total = len(self._tokens)
        self._idf = {t: math.log(1 + (total - n + 0.5) / (n + 0.5)) for t, n in frequency.items()}

    def search(self, query: str, top_k: int = 4) -> list[Chunk]:
        """Return the best-matching sections, highest score first; no match returns nothing."""
        terms = _tokenize(query)
        scored = []
        for chunk, tokens in zip(self.chunks, self._tokens, strict=True):
            counts = Counter(tokens)
            score = 0.0
            for term in terms:
                if term in counts:
                    norm = counts[term] + K1 * (1 - B + B * len(tokens) / self._average)
                    score += self._idf[term] * counts[term] * (K1 + 1) / norm
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _split(doc_id: str, text: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    heading, lines = "Overview", []
    for line in text.splitlines():
        if line.startswith("## "):
            _flush(chunks, doc_id, heading, lines)
            heading, lines = line[3:].strip(), []
        else:
            lines.append(line)
    _flush(chunks, doc_id, heading, lines)
    return chunks


def _flush(chunks: list[Chunk], doc_id: str, heading: str, lines: list[str]) -> None:
    body = "\n".join(lines).strip()
    if body:
        chunks.append(Chunk(doc_id, heading, body))
