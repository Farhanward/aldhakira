"""Enterprise-layer tests: config, metrics, hardened HTTP retrieval service."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from aldhakira.config import load_config
from aldhakira.index import build_index
from aldhakira.observability import Metrics, teardown_logging
from aldhakira.service import Handler, create_server
from aldhakira.version import __version__


class ConfigTests(unittest.TestCase):
    KEYS = ("ALDHAKIRA_HOME", "ALDHAKIRA_API_KEY", "ALDHAKIRA_PORT")

    def setUp(self) -> None:
        self._saved = {k: os.environ.get(k) for k in self.KEYS}

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_defaults(self) -> None:
        for key in self.KEYS:
            os.environ.pop(key, None)
        cfg = load_config()
        self.assertEqual(cfg.port, 8796)
        self.assertFalse(cfg.auth_required)

    def test_env_overrides(self) -> None:
        os.environ["ALDHAKIRA_API_KEY"] = "k"
        os.environ["ALDHAKIRA_PORT"] = "9944"
        cfg = load_config()
        self.assertTrue(cfg.auth_required)
        self.assertEqual(cfg.port, 9944)


class MetricsTests(unittest.TestCase):
    def test_percentiles_ordered(self) -> None:
        metrics = Metrics("aldhakira", __version__)
        for value in range(1, 41):
            metrics.observe_ms(float(value))
        snap = metrics.snapshot()
        self.assertLessEqual(snap["latency_ms"]["p50"], snap["latency_ms"]["p95"])
        self.assertLessEqual(snap["latency_ms"]["p95"], snap["latency_ms"]["p99"])


class ServiceTestBase(unittest.TestCase):
    api_key = ""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        tmp_path = Path(self._tmp.name)
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "carbonflow.md").write_text(
            "CarbonFlow is a Saudi automation and AI studio.\n"
            "It runs n8n and Ollama on a self-hosted server.\n"
            "Contact secret: owner@example.com should be redacted.\n",
            encoding="utf-8",
        )
        (docs / "zeed.md").write_text(
            "ZEED is a local income-generating AI system with a Qdrant knowledge base.\n",
            encoding="utf-8",
        )
        index_path = tmp_path / "index"
        build_index(docs, index_path)
        os.environ["ALDHAKIRA_INDEX"] = str(index_path)
        os.environ["ALDHAKIRA_API_KEY"] = self.api_key
        os.environ["ALDHAKIRA_LOG_DIR"] = str(tmp_path / "logs")
        self.server = create_server(host="127.0.0.1", port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        for key in ("ALDHAKIRA_INDEX", "ALDHAKIRA_API_KEY", "ALDHAKIRA_LOG_DIR"):
            os.environ.pop(key, None)
        if Handler.logger is not None:
            teardown_logging(Handler.logger)
            Handler.logger = None
        self._tmp.cleanup()

    def request_raw(self, path: str, payload: dict | None = None, headers: dict | None = None):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, headers=headers or {})
        if data is not None:
            request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, response.read().decode("utf-8")

    def request(self, path: str, payload: dict | None = None, headers: dict | None = None):
        status, raw = self.request_raw(path, payload, headers)
        return status, json.loads(raw)


class OpenServiceTests(ServiceTestBase):
    api_key = ""

    def test_health(self) -> None:
        status, body = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["service"], "aldhakira")

    def test_ask_returns_relevant_chunk(self) -> None:
        status, body = self.request("/api/ask", {"query": "What is CarbonFlow automation studio"})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        joined = json.dumps(body, ensure_ascii=False)
        self.assertIn("CarbonFlow", joined)

    def test_search_never_returns_raw_secret(self) -> None:
        status, raw = self.request_raw("/api/search", {"query": "contact owner email"})
        self.assertEqual(status, 200)
        self.assertNotIn("owner@example.com", raw)

    def test_ask_missing_query(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request("/api/ask", {})
        self.assertEqual(ctx.exception.code, 400)

    def test_metrics_after_ask(self) -> None:
        self.request("/api/ask", {"query": "ZEED system"})
        status, metrics = self.request("/api/metrics")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(metrics["counters"].get("http_requests_total", 0), 1)


class AuthServiceTests(ServiceTestBase):
    api_key = "dhakira-secret"

    def test_rejects_missing_key(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request("/api/metrics")
        self.assertEqual(ctx.exception.code, 401)

    def test_accepts_valid_key(self) -> None:
        status, body = self.request("/api/metrics", headers={"X-API-Key": "dhakira-secret"})
        self.assertEqual(status, 200)
        self.assertEqual(body["service"], "aldhakira")

    def test_health_open_for_probes(self) -> None:
        status, body = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["auth_required"])

    def test_oversized_body_rejected(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request("/api/ask", {"query": "x" * 1_200_000}, headers={"X-API-Key": "dhakira-secret"})
        self.assertEqual(ctx.exception.code, 413)


if __name__ == "__main__":
    unittest.main()
