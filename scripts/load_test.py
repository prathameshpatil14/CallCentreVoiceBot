"""Simple concurrency load test for /v1/sessions and /turns endpoints.

Usage:
  PYTHONPATH=src python scripts/load_test.py --base-url http://127.0.0.1:8080 --users 20 --turns 10
"""

from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
from dataclasses import dataclass
from urllib import error, request


@dataclass
class RunStats:
    total_requests: int = 0
    success_requests: int = 0
    failed_requests: int = 0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0


def _post_json(url: str, payload: dict, timeout: float) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _create_session(base_url: str, timeout: float) -> str:
    req = request.Request(f"{base_url}/v1/sessions", method="POST")
    with request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
        return payload["session_id"]


def run_load(base_url: str, users: int, turns: int, timeout: float) -> RunStats:
    latencies: list[float] = []
    total_lock = threading.Lock()
    success = 0
    failed = 0

    def worker(user_id: int) -> None:
        nonlocal success, failed
        try:
            session_id = _create_session(base_url, timeout)
        except Exception:
            with total_lock:
                failed += 1
            return

        for turn in range(turns):
            text = f"user-{user_id} turn-{turn} I need support for billing"
            start = time.perf_counter()
            try:
                status, _ = _post_json(f"{base_url}/v1/sessions/{session_id}/turns", {"text": text}, timeout)
                elapsed_ms = (time.perf_counter() - start) * 1000
                with total_lock:
                    latencies.append(elapsed_ms)
                    if status == 200:
                        success += 1
                    else:
                        failed += 1
            except (error.HTTPError, error.URLError, TimeoutError):
                with total_lock:
                    failed += 1

    threads = [threading.Thread(target=worker, args=(idx,), daemon=True) for idx in range(users)]
    start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall_ms = (time.perf_counter() - start) * 1000

    latencies_sorted = sorted(latencies)
    if latencies_sorted:
        p50 = latencies_sorted[int(0.50 * (len(latencies_sorted) - 1))]
        p95 = latencies_sorted[int(0.95 * (len(latencies_sorted) - 1))]
        p99 = latencies_sorted[int(0.99 * (len(latencies_sorted) - 1))]
    else:
        p50 = p95 = p99 = 0.0

    stats = RunStats(
        total_requests=users * turns,
        success_requests=success,
        failed_requests=failed,
        p50_ms=round(p50, 2),
        p95_ms=round(p95, 2),
        p99_ms=round(p99, 2),
    )
    print(json.dumps({
        "duration_ms": round(wall_ms, 2),
        "users": users,
        "turns_per_user": turns,
        "total_requests": stats.total_requests,
        "success_requests": stats.success_requests,
        "failed_requests": stats.failed_requests,
        "success_rate": round((stats.success_requests / max(1, stats.total_requests)) * 100, 2),
        "latency_ms": {
            "p50": stats.p50_ms,
            "p95": stats.p95_ms,
            "p99": stats.p99_ms,
            "mean": round(statistics.mean(latencies_sorted), 2) if latencies_sorted else 0.0,
        },
    }, indent=2))
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a quick load test against the voice bot API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--turns", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    stats = run_load(args.base_url.rstrip("/"), args.users, args.turns, args.timeout)
    return 0 if stats.failed_requests == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
