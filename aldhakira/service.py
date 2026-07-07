"""Aldhakira retrieval as a local HTTP service.

``POST /api/ask`` and ``POST /api/search`` accept ``{"query": "...", "top_k": 5}``
and answer from the local index with citations. The index is loaded once at
startup (``ALDHAKIRA_INDEX`` overrides the directory, default
``<project>/indexes/default``) and kept in memory for production latency.
"""

from __future__ import annotations

import os
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT
from .http_base import BaseServiceHandler, build_server
from .index import MemoryIndex

_INDEX: MemoryIndex | None = None


def index_dir() -> Path:
    raw = os.environ.get("ALDHAKIRA_INDEX", "").strip()
    return Path(raw) if raw else PROJECT_ROOT / "indexes" / "default"


def _query_from(data: dict[str, Any]) -> tuple[str, int]:
    query = str(data.get("query") or "").strip()
    top_k = data.get("top_k") or 5
    try:
        top_k = max(1, min(50, int(top_k)))
    except (TypeError, ValueError):
        top_k = 5
    return query, top_k


def _ask_route(data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    query, top_k = _query_from(data)
    if not query:
        return 400, {"ok": False, "error": "missing 'query'"}
    if _INDEX is None:
        return 503, {"ok": False, "error": f"index not loaded: {index_dir()}"}
    return 200, {"ok": True, **_INDEX.answer(query, top_k=top_k)}


def _search_route(data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    query, top_k = _query_from(data)
    if not query:
        return 400, {"ok": False, "error": "missing 'query'"}
    if _INDEX is None:
        return 503, {"ok": False, "error": f"index not loaded: {index_dir()}"}
    hits = _INDEX.search(query, top_k=top_k)
    return 200, {"ok": True, "hits": [hit.to_dict() for hit in hits]}


class Handler(BaseServiceHandler):
    post_routes = {
        "/api/ask": staticmethod(_ask_route),
        "/api/search": staticmethod(_search_route),
    }


def create_server(host: str | None = None, port: int | None = None) -> ThreadingHTTPServer:
    global _INDEX
    target = index_dir()
    _INDEX = MemoryIndex.load(target) if target.exists() else None
    return build_server(Handler, host=host, port=port)


def run_server(host: str | None = None, port: int | None = None) -> None:
    from .version import __version__

    server = create_server(host=host, port=port)
    print(f"aldhakira service v{__version__}: http://{server.server_address[0]}:{server.server_address[1]}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
