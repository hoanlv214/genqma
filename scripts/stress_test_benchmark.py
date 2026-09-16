#!/usr/bin/env python3
"""
stress_test_benchmark.py

Benchmarks server throughput, concurrency, latency percentiles, and failure points:
1. High-concurrency read throughput (GET /api/v1/health, /api/v1/config)
2. Recommendation pipeline with caching (GET /api/v1/agent/recommendations)
3. Autonomous Decision pipeline (POST /api/v1/agent/decision)
4. Worker Session Queue throughput (POST /api/v1/sessions/acquire-lease)
"""

import asyncio
import time
import statistics
import httpx

BASE_URL = "http://127.0.0.1:8000"
INTERNAL_SECRET = "pass"


async def benchmark_endpoint(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    json_body: dict = None,
    headers: dict = None,
    total_requests: int = 100,
    concurrency: int = 10,
    name: str = ""
):
    url = f"{BASE_URL}{path}"
    semaphore = asyncio.Semaphore(concurrency)
    latencies = []
    errors = 0
    status_codes = {}

    req_headers = {"x-benchmark-test": "1"}
    if headers:
        req_headers.update(headers)

    async def single_request():
        nonlocal errors
        async with semaphore:
            start = time.perf_counter()
            try:
                if method == "GET":
                    resp = await client.get(url, headers=req_headers)
                else:
                    resp = await client.post(url, json=json_body, headers=req_headers)
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)
                status_codes[resp.status_code] = status_codes.get(resp.status_code, 0) + 1
                if resp.status_code >= 400:
                    errors += 1
            except Exception as e:
                errors += 1
                latencies.append(10000.0)
                status_codes["ERR"] = status_codes.get("ERR", 0) + 1

    start_time = time.perf_counter()
    tasks = [asyncio.create_task(single_request()) for _ in range(total_requests)]
    await asyncio.gather(*tasks)
    total_time = time.perf_counter() - start_time

    rps = total_requests / total_time if total_time > 0 else 0
    sorted_lat = sorted(latencies)
    p50 = statistics.median(sorted_lat) if sorted_lat else 0
    p95 = sorted_lat[int(len(sorted_lat) * 0.95)] if sorted_lat else 0
    p99 = sorted_lat[int(len(sorted_lat) * 0.99)] if sorted_lat else 0
    min_lat = sorted_lat[0] if sorted_lat else 0
    max_lat = sorted_lat[-1] if sorted_lat else 0

    return {
        "name": name or path,
        "total_requests": total_requests,
        "concurrency": concurrency,
        "duration_sec": round(total_time, 2),
        "rps": round(rps, 1),
        "min_ms": round(min_lat, 1),
        "p50_ms": round(p50, 1),
        "p95_ms": round(p95, 1),
        "p99_ms": round(p99, 1),
        "max_ms": round(max_lat, 1),
        "errors": errors,
        "error_pct": round((errors / total_requests) * 100, 1),
        "status_codes": status_codes,
    }


async def run_all_benchmarks():
    print("=================================================================================")
    print("  QMA SERVER CONCURRENCY & STRESS TEST BENCHMARK")
    print("=================================================================================")
    print(f"Target URL: {BASE_URL}")

    limits = httpx.Limits(max_connections=200, max_keepalive_connections=50)
    timeout = httpx.Timeout(20.0, connect=10.0)

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        # Warm-up
        try:
            r = await client.get(f"{BASE_URL}/api/v1/health")
            if r.status_code != 200:
                print(f"Warm-up failed with status {r.status_code}")
        except Exception as e:
            print(f"Server not responding on {BASE_URL}: {e}")
            return

        results = []

        # Test 1: Health (baseline server event loop throughput)
        print("\n[Bench 1] GET /api/v1/health (1000 requests, concurrency=50)")
        res1 = await benchmark_endpoint(
            client, "GET", "/api/v1/health",
            total_requests=1000, concurrency=50, name="Health Check"
        )
        results.append(res1)

        # Test 2: Platform Config (reads config, balance cache, provider registry)
        print("\n[Bench 2] GET /api/v1/config (200 requests, concurrency=25)")
        res2 = await benchmark_endpoint(
            client, "GET", "/api/v1/config",
            total_requests=200, concurrency=25, name="Platform Config"
        )
        results.append(res2)

        # Test 3: Recommendations (cached market anomaly scoring)
        print("\n[Bench 3] GET /api/v1/agent/recommendations (100 requests, concurrency=10)")
        res3 = await benchmark_endpoint(
            client, "GET", "/api/v1/agent/recommendations?limit=8",
            total_requests=100, concurrency=10, name="Agent Recommendations"
        )
        results.append(res3)

        # Test 4: Decision Engine (deterministic policy planning)
        print("\n[Bench 4] POST /api/v1/agent/decision (50 requests, concurrency=10)")
        decision_body = {
            "prompt": "Find top funding rate divergence under $0.005",
            "budget_usdc": 0.01,
            "max_price_usdc": 0.005,
            "limit": 8,
            "use_llm": False,
        }
        res4 = await benchmark_endpoint(
            client, "POST", "/api/v1/agent/decision",
            json_body=decision_body, total_requests=50, concurrency=10, name="Decision Engine"
        )
        results.append(res4)

        # Test 5: Worker Session Queue Lease Acquisition (Supabase RPC concurrency)
        print("\n[Bench 5] POST /api/v1/sessions/acquire-lease (50 requests, concurrency=10)")
        lease_body = {
            "worker_id": "bench_worker_1",
            "lease_duration_sec": 60,
        }
        res5 = await benchmark_endpoint(
            client, "POST", "/api/v1/sessions/acquire-lease",
            json_body=lease_body, headers={"x-qma-internal-secret": INTERNAL_SECRET},
            total_requests=50, concurrency=10, name="Worker Acquire Lease"
        )
        results.append(res5)

        # Summary Table
        print("\n" + "=" * 105)
        print(f"{'Endpoint':<25} | {'Conc':<5} | {'Reqs':<6} | {'RPS':<8} | {'p50 (ms)':<9} | {'p95 (ms)':<9} | {'Max (ms)':<9} | {'Err %':<6}")
        print("-" * 105)
        for r in results:
            print(f"{r['name']:<25} | {r['concurrency']:<5} | {r['total_requests']:<6} | {r['rps']:<8} | {r['p50_ms']:<9} | {r['p95_ms']:<9} | {r['max_ms']:<9} | {r['error_pct']:<6}")
        print("=" * 105)


if __name__ == "__main__":
    asyncio.run(run_all_benchmarks())
