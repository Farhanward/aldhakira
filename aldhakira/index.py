from __future__ import annotations

import heapq
import json
import math
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ingest import document_chunks
from .models import Chunk, SearchHit
from .text import token_counts, tokens


CHUNKS_FILE = "chunks.jsonl"
POSTINGS_FILE = "postings.json"
META_FILE = "meta.json"


def build_index(source: str | Path, index_dir: str | Path, *, limit: int = 0, max_chars: int = 1400) -> dict[str, Any]:
    started = time.perf_counter()
    root = Path(index_dir)
    root.mkdir(parents=True, exist_ok=True)
    postings: dict[str, dict[str, int]] = defaultdict(dict)
    doc_lengths: dict[str, int] = {}
    redactions = 0
    chunk_count = 0
    source_count = set()
    with (root / CHUNKS_FILE).open("w", encoding="utf-8") as chunk_out:
        for item in document_chunks(source, limit=limit, max_chars=max_chars):
            chunk = Chunk(
                id=chunk_count,
                source=item["source"],
                title=item["title"],
                text=item["text"],
                token_count=item["token_count"],
                metadata=item["metadata"],
            )
            counts = token_counts(chunk.text)
            for token, count in counts.items():
                postings[token][str(chunk.id)] = int(count)
            doc_lengths[str(chunk.id)] = max(1, chunk.token_count)
            redactions += len(chunk.metadata.get("redactions") or [])
            source_count.add(chunk.source.split("#row=")[0])
            chunk_out.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
            chunk_count += 1
    meta = {
        "source": str(Path(source).resolve(strict=False)),
        "chunks": chunk_count,
        "sources": len(source_count),
        "tokens": len(postings),
        "redactions": redactions,
        "max_chars": max_chars,
        "elapsed_seconds": time.perf_counter() - started,
    }
    (root / POSTINGS_FILE).write_text(json.dumps(postings, ensure_ascii=False), encoding="utf-8")
    (root / META_FILE).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def _load_chunks(index_dir: str | Path) -> dict[int, Chunk]:
    chunks: dict[int, Chunk] = {}
    with (Path(index_dir) / CHUNKS_FILE).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                chunk = Chunk.from_dict(json.loads(line))
                chunks[chunk.id] = chunk
    return chunks


def _load_index(index_dir: str | Path) -> tuple[dict[int, Chunk], dict[str, dict[str, int]], dict[str, Any]]:
    root = Path(index_dir)
    chunks = _load_chunks(root)
    postings = json.loads((root / POSTINGS_FILE).read_text(encoding="utf-8"))
    meta = json.loads((root / META_FILE).read_text(encoding="utf-8"))
    return chunks, postings, meta


@dataclass
class MemoryIndex:
    chunks: dict[int, Chunk]
    postings: dict[str, dict[str, int]]
    meta: dict[str, Any]
    avg_len: float

    @classmethod
    def load(cls, index_dir: str | Path) -> "MemoryIndex":
        chunks, postings, meta = _load_index(index_dir)
        avg_len = sum(chunk.token_count for chunk in chunks.values()) / max(1, len(chunks))
        return cls(chunks, postings, meta, avg_len)

    def search(self, query: str, *, top_k: int = 5) -> list[SearchHit]:
        q_counts = Counter(tokens(query))
        if not q_counts:
            return []
        scores: dict[int, float] = defaultdict(float)
        matched: dict[int, set[str]] = defaultdict(set)
        n_docs = max(1, int(self.meta.get("chunks") or len(self.chunks)))
        k1 = 1.4
        b = 0.75
        available_terms: list[tuple[int, str, int]] = []
        skipped_common: list[tuple[int, str, int]] = []
        for token, qtf in q_counts.items():
            posting = self.postings.get(token)
            if not posting:
                continue
            item = (len(posting), token, qtf)
            if len(posting) / n_docs > 0.20 and len(q_counts) > 1:
                skipped_common.append(item)
            else:
                available_terms.append(item)
        terms = sorted(available_terms or skipped_common)[:10]
        for df, token, qtf in terms:
            posting = self.postings[token]
            df = len(posting)
            idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
            for raw_id, tf in posting.items():
                chunk_id = int(raw_id)
                length = self.chunks[chunk_id].token_count
                denom = tf + k1 * (1 - b + b * (length / max(1.0, self.avg_len)))
                scores[chunk_id] += idf * ((tf * (k1 + 1)) / denom) * qtf
                matched[chunk_id].add(token)
        winners = heapq.nlargest(top_k, scores.items(), key=lambda item: item[1])
        return [SearchHit(self.chunks[chunk_id], score, sorted(matched[chunk_id])) for chunk_id, score in winners if score > 0]

    def answer(self, query: str, *, top_k: int = 5) -> dict[str, Any]:
        hits = self.search(query, top_k=top_k)
        if not hits:
            return {"query": query, "answer": "لم أجد مقاطع مناسبة في الذاكرة المحلية.", "citations": []}
        lines = ["أفضل المقاطع المسترجعة من الذاكرة المحلية:"]
        citations = []
        for idx, hit in enumerate(hits, start=1):
            snippet = hit.chunk.text[:360].strip()
            lines.append(f"[{idx}] {hit.chunk.title}: {snippet}")
            citations.append({"rank": idx, **hit.to_dict()})
        return {"query": query, "answer": "\n".join(lines), "citations": citations}


def search(index_dir: str | Path, query: str, *, top_k: int = 5) -> list[SearchHit]:
    return MemoryIndex.load(index_dir).search(query, top_k=top_k)


def answer(index_dir: str | Path, query: str, *, top_k: int = 5) -> dict[str, Any]:
    return MemoryIndex.load(index_dir).answer(query, top_k=top_k)
