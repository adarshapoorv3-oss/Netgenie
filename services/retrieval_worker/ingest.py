"""
Turns the markdown runbooks in data/runbooks/ into retrievable chunks.

Chunking strategy: split on level-2 markdown headings ("## ...") so each
chunk is one coherent procedure step (Detection / Immediate Actions /
Escalation / ...), which keeps retrieved context short and on-topic --
important when running small CPU-friendly models.

Retrieval uses BM25 (rank_bm25) instead of dense embeddings by default:
it needs no model download, runs in milliseconds on a laptop CPU, and is
a defensible production choice for short, keyword-rich operational docs
like runbooks and alarm procedures. Swap in a dense embedding service
behind the same /v1/retrieve contract for semantic search if needed.
"""
import os
import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

TOKEN_RE = re.compile(r"[a-zA-Z0-9%]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


@dataclass
class Chunk:
    source: str
    heading: str
    text: str


def load_chunks(runbooks_dir: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    if not os.path.isdir(runbooks_dir):
        return chunks

    for fname in sorted(os.listdir(runbooks_dir)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(runbooks_dir, fname)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        doc_title = title_match.group(1).strip() if title_match else fname

        sections = re.split(r"^##\s+(.+)$", content, flags=re.MULTILINE)
        # sections[0] is preamble before first "## heading"
        if sections[0].strip():
            chunks.append(Chunk(source=fname, heading=doc_title, text=sections[0].strip()))
        for i in range(1, len(sections), 2):
            heading = sections[i].strip()
            body = sections[i + 1].strip() if i + 1 < len(sections) else ""
            if body:
                chunks.append(
                    Chunk(source=fname, heading=f"{doc_title} \u2192 {heading}", text=body)
                )
    return chunks


class BM25Index:
    def __init__(self, runbooks_dir: str):
        self.chunks = load_chunks(runbooks_dir)
        corpus = [tokenize(c.text) for c in self.chunks]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def search(self, query: str, top_k: int = 3):
        if not self._bm25:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for idx in ranked[:top_k]:
            if scores[idx] <= 0:
                continue
            c = self.chunks[idx]
            results.append(
                {
                    "source": c.source,
                    "heading": c.heading,
                    "text": c.text,
                    "score": round(float(scores[idx]), 3),
                }
            )
        return results
