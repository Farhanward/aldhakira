from __future__ import annotations

import json
import statistics
import time
import tracemalloc
from pathlib import Path
from typing import Any

from .index import MemoryIndex, build_index


def _p(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))]


def _iter_jsonl(path: str | Path, limit: int = 0):
    with Path(path).open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if limit and index >= limit:
                break
            if line.strip():
                yield index, json.loads(line)


def _query_from_record(record: dict[str, Any]) -> str:
    text = str(record.get("instruction") or record.get("text") or record.get("content") or "")
    words = text.split()
    return " ".join(words[:14]) if words else str(record.get("category") or "")


def benchmark(source: str | Path, index_dir: str | Path, *, limit: int = 12000, top_k: int = 5) -> dict[str, Any]:
    index_meta = build_index(source, index_dir, limit=limit)
    memory = MemoryIndex.load(index_dir)
    latencies: list[float] = []
    hits = misses = errors = 0
    started = time.perf_counter()
    tracemalloc.start()
    for row_index, record in _iter_jsonl(source, limit=limit):
        query = _query_from_record(record)
        expected = f"#row={row_index}"
        t0 = time.perf_counter()
        try:
            result = memory.search(query, top_k=top_k)
            if any(expected in hit.chunk.source for hit in result):
                hits += 1
            else:
                misses += 1
        except Exception:
            errors += 1
            misses += 1
        latencies.append((time.perf_counter() - t0) * 1000)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    processed = hits + misses
    return {
        "source": str(Path(source).resolve()),
        "index": str(Path(index_dir).resolve()),
        "index_meta": index_meta,
        "processed": processed,
        "top_k": top_k,
        "recall_at_k": hits / processed if processed else 0.0,
        "hits": hits,
        "misses": misses,
        "errors": errors,
        "latency_ms": {
            "mean": statistics.fmean(latencies) if latencies else 0.0,
            "p50": _p(latencies, 50),
            "p95": _p(latencies, 95),
            "p99": _p(latencies, 99),
            "max": max(latencies) if latencies else 0.0,
        },
        "memory_mb": {"current": current / 1_000_000, "peak": peak / 1_000_000},
        "elapsed_seconds": time.perf_counter() - started,
        "collapse_check": {"passed": errors == 0, "criteria": "errors == 0"},
    }


def stress(index_dir: str | Path, queries: list[str], *, repeat: int = 3, top_k: int = 5) -> dict[str, Any]:
    latencies: list[float] = []
    errors = empty = 0
    started = time.perf_counter()
    tracemalloc.start()
    memory = MemoryIndex.load(index_dir)
    for _ in range(repeat):
        for query in queries:
            t0 = time.perf_counter()
            try:
                result = memory.answer(query, top_k=top_k)
                if not result["citations"]:
                    empty += 1
            except Exception:
                errors += 1
            latencies.append((time.perf_counter() - t0) * 1000)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "index": str(Path(index_dir).resolve()),
        "queries": len(queries),
        "repeat": repeat,
        "processed": len(queries) * repeat,
        "errors": errors,
        "empty": empty,
        "latency_ms": {
            "mean": statistics.fmean(latencies) if latencies else 0.0,
            "p95": _p(latencies, 95),
            "p99": _p(latencies, 99),
            "max": max(latencies) if latencies else 0.0,
        },
        "memory_mb": {"current": current / 1_000_000, "peak": peak / 1_000_000},
        "elapsed_seconds": time.perf_counter() - started,
        "collapse_check": {"passed": errors == 0, "criteria": "errors == 0"},
    }
