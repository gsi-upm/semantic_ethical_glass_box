"""Report query latency at the current KG size (standalone).

Run after the KG holds a representative volume to get the per-report latency
table for the paper.
"""
import os

from segb_bench import config as C
from segb_bench.metrics import summarize
from segb_bench.sparql import REPORTS, count_kg, run_query


def main() -> None:
    kg = count_kg(C.BASE_URL)
    print(f"KG size: {kg} triples\n")
    print(f"{'report':<20}{'rows':>6}{'p50_ms':>10}{'p95_ms':>10}{'mean_ms':>10}")
    for name, q in REPORTS.items():
        lats, rows = [], None
        for _ in range(C.QUERY_REPEATS):
            lat, status, n = run_query(C.BASE_URL, q)
            lats.append(lat)
            rows = n
        s = summarize(lats)
        print(f"{name:<20}{str(rows):>6}{s['p50']:>10}{s['p95']:>10}{s['mean']:>10}")


if __name__ == "__main__":
    main()
