"""Aggregate per-robot CSVs into the numbers that go in the paper.

For ingestion CSVs (B1/B2): per-(setup,mode) latency percentiles, aggregate
throughput, error rate. For shared-context CSVs (B3): convergence check.

Usage:
  python aggregate.py out/robot*_B2.csv            # ingestion
  python aggregate.py --shared out/robot*_B3.csv   # convergence
"""
import argparse
import csv
import glob

from segb_bench.metrics import summarize


def _read(paths):
    rows = []
    for pat in paths:
        for path in glob.glob(pat):
            with open(path, newline="") as fh:
                for r in csv.DictReader(fh):
                    r["_file"] = path
                    rows.append(r)
    return rows


def aggregate_ingest(paths):
    rows = _read(paths)
    ok = [r for r in rows if r.get("ok") in ("True", "true", "1")]
    lats = [float(r["latency_ms"]) for r in ok]
    robots = sorted(set(r["robot_id"] for r in rows))
    print(f"files          : {len(set(r['_file'] for r in rows))}")
    print(f"robots         : {robots}")
    print(f"total requests : {len(rows)}  ok={len(ok)}  errors={len(rows)-len(ok)}")
    print("aggregate latency (ms):")
    for k, v in summarize(lats).items():
        print(f"  {k:6s}: {v}")
    # per-robot view
    for rb in robots:
        rl = [float(r["latency_ms"]) for r in ok if r["robot_id"] == rb]
        s = summarize(rl)
        print(f"  {rb}: n={s.get('n')} p50={s.get('p50')} p95={s.get('p95')}")


def aggregate_shared(paths):
    rows = _read(paths)
    iris = set(r["shared_event_uri"] for r in rows)
    robots = sorted(set(r["robot_id"] for r in rows))
    lats = [float(r["latency_ms"]) for r in rows]
    print(f"robots                 : {robots}")
    print(f"total resolves         : {len(rows)}")
    print(f"distinct canonical IRIs: {len(iris)}  (1 == full convergence)")
    if len(iris) > 1:
        print("  WARNING: divergence detected:")
        for i in iris:
            print("   ", i)
    print("resolve latency (ms):")
    for k, v in summarize(lats).items():
        print(f"  {k:6s}: {v}")
    print("\nAlso check backend: GET /shared-context/stats and "
          "/shared-context/review/pending for merge/duplicate cases.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--shared", action="store_true", help="treat inputs as B3 convergence CSVs")
    args = ap.parse_args()
    if args.shared:
        aggregate_shared(args.paths)
    else:
        aggregate_ingest(args.paths)


if __name__ == "__main__":
    main()
