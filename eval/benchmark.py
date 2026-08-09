"""
NetGenie evaluation harness.

Mirrors the three metric families the challenge brief asks for
(response time, scalability under concurrent requests, and answer
usefulness) using the same spirit as OPEA's GenAIEval: latency
percentiles, throughput under load, and a lightweight accuracy check.

Usage:
    python eval/benchmark.py --url http://localhost:9000 --concurrency 1 5 10
"""
import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx

HERE = Path(__file__).parent


def load_queries():
    with open(HERE / "eval_queries.json") as f:
        return json.load(f)


async def run_one(client: httpx.AsyncClient, url: str, item: dict):
    t0 = time.perf_counter()
    try:
        resp = await client.post(f"{url}/v1/chat", json={"message": item["question"]}, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        latency = time.perf_counter() - t0
        answer_lc = data.get("answer", "").lower()
        hit = any(kw.lower() in answer_lc for kw in item["expect_any"])
        return {"ok": True, "latency": latency, "hit": hit, "question": item["question"]}
    except Exception as exc:
        return {"ok": False, "latency": time.perf_counter() - t0, "hit": False, "question": item["question"], "error": str(exc)}


async def run_concurrency_level(url: str, queries: list, concurrency: int):
    async with httpx.AsyncClient() as client:
        sem = asyncio.Semaphore(concurrency)

        async def bound_run(item):
            async with sem:
                return await run_one(client, url, item)

        t0 = time.perf_counter()
        results = await asyncio.gather(*(bound_run(q) for q in queries))
        wall = time.perf_counter() - t0

    latencies = sorted(r["latency"] for r in results)
    ok = [r for r in results if r["ok"]]
    hits = [r for r in results if r["hit"]]

    def pct(p):
        if not latencies:
            return 0.0
        idx = min(len(latencies) - 1, int(len(latencies) * p))
        return latencies[idx]

    return {
        "concurrency": concurrency,
        "n": len(results),
        "success_rate": round(len(ok) / len(results), 3) if results else 0,
        "accuracy_keyword_hit_rate": round(len(hits) / len(results), 3) if results else 0,
        "throughput_rps": round(len(results) / wall, 2) if wall > 0 else 0,
        "p50_s": round(pct(0.5), 3),
        "p95_s": round(pct(0.95), 3),
        "mean_s": round(statistics.mean(latencies), 3) if latencies else 0,
        "wall_s": round(wall, 3),
        "failures": [r for r in results if not r["ok"]],
    }


def to_markdown(all_results: list, url: str) -> str:
    lines = [
        "# NetGenie Evaluation Report",
        "",
        f"Target: `{url}`  \nQueries per run: {all_results[0]['n'] if all_results else 0}",
        "",
        "| Concurrency | Success rate | Keyword-hit accuracy | Throughput (req/s) | p50 latency (s) | p95 latency (s) |",
        "|---|---|---|---|---|---|",
    ]
    for r in all_results:
        lines.append(
            f"| {r['concurrency']} | {r['success_rate']*100:.0f}% | {r['accuracy_keyword_hit_rate']*100:.0f}% "
            f"| {r['throughput_rps']} | {r['p50_s']} | {r['p95_s']} |"
        )
    lines.append("")
    lines.append(
        "Keyword-hit accuracy checks whether the synthesized answer contains at least one "
        "expected keyword per question — a coarse but dependency-free proxy for relevance, "
        "meant to be replaced with BLEU/ROUGE/LLM-judge scoring (see GenAIEval) once a real "
        "LLM backend is attached (MOCK_LLM=false)."
    )
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:9000")
    parser.add_argument("--concurrency", nargs="+", type=int, default=[1, 5, 10])
    args = parser.parse_args()

    queries = load_queries()
    all_results = []
    for c in args.concurrency:
        print(f"Running at concurrency={c} ...")
        result = await run_concurrency_level(args.url, queries, c)
        all_results.append(result)
        print(json.dumps({k: v for k, v in result.items() if k != "failures"}, indent=2))

    report = to_markdown(all_results, args.url)
    out_path = HERE / "report.md"
    out_path.write_text(report)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
