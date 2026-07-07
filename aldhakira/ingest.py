from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from .text import chunk_text, normalize, redact, tokens


TEXT_SUFFIXES = {".txt", ".md", ".rst", ".log"}
JSON_TEXT_KEYS = ("instruction", "context", "response", "output", "text", "content", "title", "body", "summary")


def _record_text(record: dict[str, Any]) -> str:
    parts = []
    for key in JSON_TEXT_KEYS:
        value = record.get(key)
        if value is not None:
            parts.append(str(value))
    if not parts:
        parts = [json.dumps(record, ensure_ascii=False, sort_keys=True)]
    return "\n".join(parts)


def _record_title(record: dict[str, Any], fallback: str) -> str:
    for key in ("title", "instruction", "id", "category"):
        value = str(record.get(key) or "").strip()
        if value:
            return value[:120]
    return fallback


def iter_documents(path: str | Path, *, limit: int = 0) -> Iterable[dict[str, Any]]:
    source = Path(path)
    count = 0
    files = sorted(source.rglob("*")) if source.is_dir() else [source]
    for file in files:
        if not file.is_file():
            continue
        suffix = file.suffix.lower()
        if suffix in TEXT_SUFFIXES:
            yield {"source": str(file.resolve()), "title": file.name, "text": file.read_text(encoding="utf-8", errors="ignore"), "metadata": {"kind": suffix.lstrip(".")}}
            count += 1
        elif suffix == ".jsonl":
            with file.open("r", encoding="utf-8") as handle:
                for row_index, line in enumerate(handle):
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    title = _record_title(record, f"{file.name}#{row_index}")
                    yield {
                        "source": f"{file.resolve()}#row={row_index}",
                        "title": title,
                        "text": _record_text(record),
                        "metadata": {"kind": "jsonl", "row": row_index, "category": record.get("category")},
                    }
                    count += 1
                    if limit and count >= limit:
                        return
        elif suffix == ".json":
            data = json.loads(file.read_text(encoding="utf-8"))
            records = data if isinstance(data, list) else [data]
            for row_index, record in enumerate(records):
                if not isinstance(record, dict):
                    record = {"content": record}
                title = _record_title(record, f"{file.name}#{row_index}")
                yield {"source": f"{file.resolve()}#row={row_index}", "title": title, "text": _record_text(record), "metadata": {"kind": "json", "row": row_index}}
                count += 1
                if limit and count >= limit:
                    return
        elif suffix == ".csv":
            with file.open("r", encoding="utf-8", newline="") as handle:
                for row_index, record in enumerate(csv.DictReader(handle)):
                    title = _record_title(record, f"{file.name}#{row_index}")
                    yield {"source": f"{file.resolve()}#row={row_index}", "title": title, "text": _record_text(record), "metadata": {"kind": "csv", "row": row_index}}
                    count += 1
                    if limit and count >= limit:
                        return
        if limit and count >= limit:
            return


def document_chunks(path: str | Path, *, limit: int = 0, max_chars: int = 1400) -> Iterable[dict[str, Any]]:
    for doc in iter_documents(path, limit=limit):
        safe_text, findings = redact(normalize(doc["text"]))
        for part_index, chunk in enumerate(chunk_text(safe_text, max_chars=max_chars)):
            chunk_tokens = tokens(chunk)
            if not chunk_tokens:
                continue
            metadata = dict(doc.get("metadata") or {})
            metadata.update({"part": part_index, "redactions": findings})
            yield {
                "source": doc["source"],
                "title": doc["title"],
                "text": chunk,
                "token_count": len(chunk_tokens),
                "metadata": metadata,
            }

