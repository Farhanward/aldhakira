from __future__ import annotations


def benchmark_markdown(summary: dict) -> str:
    lines = [
        "# تقرير الذاكرة",
        "",
        f"- المصدر: `{summary.get('source')}`",
        f"- الفهرس: `{summary.get('index')}`",
        f"- المقاطع: `{summary.get('index_meta', {}).get('chunks', 0)}`",
        f"- المعالجة: `{summary.get('processed', 0)}`",
        f"- Recall@{summary.get('top_k', 5)}: `{summary.get('recall_at_k', 0):.2%}`",
        f"- الأخطاء: `{summary.get('errors', 0)}`",
        f"- p99: `{summary.get('latency_ms', {}).get('p99', 0):.3f}ms`",
        f"- peak memory: `{summary.get('memory_mb', {}).get('peak', 0):.2f}MB`",
        "",
    ]
    return "\n".join(lines)

