"""Latency records, distribution summaries and CSV I/O."""
from __future__ import annotations

import csv
import statistics
from dataclasses import asdict, dataclass, fields


@dataclass
class IngestRecord:
    run_id: str
    setup: str               # "single" | "multi"
    mode: str                # "realistic" | "saturation" | "shared_context"
    robot_id: str
    seq: int
    n_triples: int           # triples in this payload
    payload_bytes: int
    cumulative_triples: int  # KG size BEFORE this insert (scalability x-axis)
    latency_ms: float        # client-side round-trip
    http_status: int
    ok: bool


def percentile(xs, q: float) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    k = (len(s) - 1) * q
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def summarize(latencies) -> dict:
    xs = list(latencies)
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "mean": round(statistics.fmean(xs), 2),
        "p50": round(percentile(xs, 0.50), 2),
        "p95": round(percentile(xs, 0.95), 2),
        "p99": round(percentile(xs, 0.99), 2),
        "min": round(min(xs), 2),
        "max": round(max(xs), 2),
        "stdev": round(statistics.pstdev(xs), 2) if len(xs) > 1 else 0.0,
    }


def write_csv(path, records) -> None:
    cols = [f.name for f in fields(IngestRecord)]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in records:
            w.writerow(asdict(r))


def read_csv(path) -> list[dict]:
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))
