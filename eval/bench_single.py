"""Setup A (single client): ingestion latency + scalability.

A1  realistic timing  -> online ingestion latency baseline
A2  saturation        -> service time / sustained throughput
A3  scalability sweep -> ingestion & query latency vs KG size (0 -> target)

Outputs:
  out/single_A1.csv, out/single_A2.csv   (per-insert IngestRecord)
  out/single_A3_ingest.csv               (per-insert, annotated with KG size)
  out/single_A3_query.csv                (query latency per checkpoint/size)
"""
import csv
import os
import time
import uuid

from segb_bench import config as C
from segb_bench.metrics import IngestRecord, summarize, write_csv
from segb_bench.replay import Capture, load_capture, replay, reset_graph
from segb_bench.sparql import REPORTS, count_kg, run_query

OUT = "out"


def _ok_latencies(records: list[IngestRecord]) -> list[float]:
    return [r.latency_ms for r in records if r.ok]


def _print_summary(label: str, records: list[IngestRecord]) -> None:
    print(f"\n== {label} ==")
    s = summarize(_ok_latencies(records))
    errors = sum(1 for r in records if not r.ok)
    for k, v in s.items():
        print(f"  {k:6s}: {v}")
    print(f"  errors: {errors}/{len(records)}")


def run_warmup(cap: Capture) -> None:
    recs: list[IngestRecord] = []
    while len(recs) < C.WARMUP_INSERTS:
        replay(C.BASE_URL, cap, setup="single", mode="saturation",
               robot_id="warmup", run_id="warmup", data_prefixes=C.DATA_PREFIXES,
               rewrite=True, records=recs)
    print(f"warmup done ({len(recs)} inserts discarded)")


def run_condition(cap: Capture, mode: str, min_samples: int, tag: str):
    reset_graph(C.BASE_URL)
    run_warmup(cap)
    reset_graph(C.BASE_URL)
    recs: list[IngestRecord] = []
    cumulative = 0
    while len(recs) < min_samples:
        _, cumulative = replay(
            C.BASE_URL, cap, setup="single", mode=mode, robot_id="robot1",
            run_id=tag, data_prefixes=C.DATA_PREFIXES, gap_cap=C.GAP_CAP_S,
            rewrite=True, records=recs, cumulative0=cumulative,
        )
    write_csv(f"{OUT}/single_{tag}.csv", recs)
    _print_summary(tag, recs)
    return recs


def run_scalability(cap: Capture):
    reset_graph(C.BASE_URL)
    run_warmup(cap)
    reset_graph(C.BASE_URL)

    ingest: list[IngestRecord] = []
    query_rows = []
    cumulative = 0
    next_checkpoint = C.SCALABILITY_CHECKPOINT_TRIPLES

    while cumulative < C.SCALABILITY_TARGET_TRIPLES:
        _, cumulative = replay(
            C.BASE_URL, cap, setup="single", mode="saturation", robot_id="robot1",
            run_id="A3", data_prefixes=C.DATA_PREFIXES, rewrite=True,
            records=ingest, cumulative0=cumulative,
        )
        if cumulative >= next_checkpoint:
            kg = count_kg(C.BASE_URL)
            for name, q in REPORTS.items():
                lats = []
                rows = None
                for _ in range(C.QUERY_REPEATS):
                    lat, status, n = run_query(C.BASE_URL, q)
                    lats.append(lat)
                    rows = n
                s = summarize(lats)
                query_rows.append({
                    "kg_triples": kg, "report": name, "rows": rows,
                    "p50_ms": s["p50"], "p95_ms": s["p95"], "mean_ms": s["mean"],
                })
            print(f"checkpoint @ ~{kg} triples done")
            next_checkpoint += C.SCALABILITY_CHECKPOINT_TRIPLES

    write_csv(f"{OUT}/single_A3_ingest.csv", ingest)
    with open(f"{OUT}/single_A3_query.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(query_rows[0].keys()))
        w.writeheader()
        w.writerows(query_rows)
    print("\nscalability sweep written to out/single_A3_*.csv")


def main():
    os.makedirs(OUT, exist_ok=True)
    cap = load_capture("capture.json")
    run_condition(cap, "realistic", C.MIN_SAMPLES, "A1")
    run_condition(cap, "saturation", C.SATURATION_SAMPLES, "A2")
    run_scalability(cap)


if __name__ == "__main__":
    main()
