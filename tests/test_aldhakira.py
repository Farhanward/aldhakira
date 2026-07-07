from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aldhakira.benchmark import benchmark
from aldhakira.index import answer, build_index, search


class AlDhakiraTests(unittest.TestCase):
    def test_build_search_and_answer(self):
        with tempfile.TemporaryDirectory(dir="C:/Projects") as tmp:
            source = Path(tmp) / "docs.jsonl"
            index = Path(tmp) / "index"
            rows = [
                {"instruction": "كيف أحمي مفاتيح API؟", "response": "استخدم خزنة أسرار ولا تضع المفاتيح في الكود."},
                {"instruction": "كيف أكتب تقرير مشروع؟", "response": "ابدأ بالهدف ثم النتائج ثم المخاطر."},
            ]
            source.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
            meta = build_index(source, index)
            self.assertEqual(meta["chunks"], 2)
            hits = search(index, "حماية مفاتيح API", top_k=1)
            self.assertEqual(len(hits), 1)
            self.assertIn("API", hits[0].chunk.text)
            result = answer(index, "تقرير مشروع", top_k=1)
            self.assertTrue(result["citations"])

    def test_redacts_secrets_before_indexing(self):
        with tempfile.TemporaryDirectory(dir="C:/Projects") as tmp:
            source = Path(tmp) / "docs.txt"
            index = Path(tmp) / "index"
            source.write_text("contact user@example.com token='sk-12345678901234567890'", encoding="utf-8")
            meta = build_index(source, index)
            self.assertGreaterEqual(meta["redactions"], 2)
            chunk_text = (index / "chunks.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("user@example.com", chunk_text)
            self.assertNotIn("sk-12345678901234567890", chunk_text)

    def test_benchmark_fixture(self):
        with tempfile.TemporaryDirectory(dir="C:/Projects") as tmp:
            source = Path(tmp) / "docs.jsonl"
            index = Path(tmp) / "index"
            rows = [
                {"instruction": "alpha beta gamma", "response": "first"},
                {"instruction": "delta epsilon zeta", "response": "second"},
                {"instruction": "privacy security audit", "response": "third"},
            ]
            source.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            summary = benchmark(source, index, limit=3, top_k=1)
            self.assertEqual(summary["processed"], 3)
            self.assertEqual(summary["errors"], 0)
            self.assertGreaterEqual(summary["recall_at_k"], 0.99)


if __name__ == "__main__":
    unittest.main()

