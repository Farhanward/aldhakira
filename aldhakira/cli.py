from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import benchmark, stress
from .index import answer, build_index, search
from .reports import benchmark_markdown


def _write_json(path: str | Path, data: dict) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="aldhakira", description="الذاكرة: عقل ثان محلي خاص.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    build = sub.add_parser("build")
    build.add_argument("--source", required=True)
    build.add_argument("--index", default="indexes/default")
    build.add_argument("--limit", type=int, default=0)
    build.add_argument("--max-chars", type=int, default=1400)

    search_cmd = sub.add_parser("search")
    search_cmd.add_argument("--index", default="indexes/default")
    search_cmd.add_argument("--query", required=True)
    search_cmd.add_argument("--top-k", type=int, default=5)

    ask = sub.add_parser("ask")
    ask.add_argument("--index", default="indexes/default")
    ask.add_argument("--query", required=True)
    ask.add_argument("--top-k", type=int, default=5)

    bench = sub.add_parser("benchmark")
    bench.add_argument("--source", default="C:/Projects/almeezan/data/external/databricks-dolly-15k/databricks-dolly-15k.jsonl")
    bench.add_argument("--index", default="indexes/dolly15k")
    bench.add_argument("--limit", type=int, default=12000)
    bench.add_argument("--top-k", type=int, default=5)
    bench.add_argument("--json-out", default="reports/aldhakira_dolly_benchmark.json")
    bench.add_argument("--report", default="reports/aldhakira_dolly_benchmark.md")

    stress_cmd = sub.add_parser("stress")
    stress_cmd.add_argument("--index", default="indexes/dolly15k")
    stress_cmd.add_argument("--query", action="append", default=[])
    stress_cmd.add_argument("--repeat", type=int, default=3)
    stress_cmd.add_argument("--json-out", default="reports/aldhakira_stress.json")
    stress_cmd.add_argument("--report", default="reports/aldhakira_stress.md")

    serve = sub.add_parser("serve")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    sub.add_parser("version")

    args = parser.parse_args(argv)
    if args.cmd == "serve":
        from .service import run_server

        run_server(host=args.host, port=args.port)
        return 0
    if args.cmd == "version":
        from .version import __version__

        print(json.dumps({"service": "aldhakira", "version": __version__}, ensure_ascii=False))
        return 0
    if args.cmd == "build":
        print(json.dumps(build_index(args.source, args.index, limit=args.limit, max_chars=args.max_chars), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "search":
        print(json.dumps([hit.to_dict() for hit in search(args.index, args.query, top_k=args.top_k)], ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "ask":
        print(json.dumps(answer(args.index, args.query, top_k=args.top_k), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "benchmark":
        summary = benchmark(args.source, args.index, limit=args.limit, top_k=args.top_k)
        _write_json(args.json_out, summary)
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(benchmark_markdown(summary), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["collapse_check"]["passed"] else 2
    if args.cmd == "stress":
        queries = args.query or [
            "how to improve machine learning training data",
            "write a professional email about project status",
            "explain privacy and security risks",
            "summarize customer support conversation",
        ]
        summary = stress(args.index, queries, repeat=args.repeat)
        _write_json(args.json_out, summary)
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(benchmark_markdown({**summary, "source": "manual queries", "top_k": 5, "recall_at_k": 0}), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["collapse_check"]["passed"] else 2
    raise ValueError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())

