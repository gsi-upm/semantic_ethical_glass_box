"""WiFi baseline: round-trip to the near-zero-work /healthz/live endpoint.

Subtract this distribution from ingestion latency to separate transport
(WiFi RTT + framework overhead) from real server-side processing. Important
here because the transport is WiFi and the RTT is unknown.
"""
import time

import requests

from segb_bench.config import BASE_URL
from segb_bench.metrics import summarize


def main(n: int = 200) -> None:
    lats = []
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            requests.get(f"{BASE_URL}/healthz/live", timeout=10)
            lats.append((time.perf_counter() - t0) * 1000.0)
        except requests.RequestException:
            pass
    print(f"network baseline /healthz/live  n={len(lats)}")
    for k, v in summarize(lats).items():
        print(f"  {k:6s}: {v}")


if __name__ == "__main__":
    main()
