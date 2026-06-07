"""Per-robot agent for the multi-robot experiments (run one copy per robot).

Modes:
  realistic / saturation  -> B1 / B2 ingestion under concurrency
  shared_context          -> B3 cross-robot convergence on the SAME event

Synchronisation: all robots are NTP-synced and started with the same
--start-at wall-clock time, so the concurrency window is aligned without
needing cross-robot clock comparison (latency is measured per robot as a local
round-trip). Each agent writes its own CSV; aggregate.py merges them.

Usage (on each robot):
  python robot_agent.py --robot-id robot1 --mode saturation \
      --start-at "2026-06-03T18:00:00" --repeats 60 --out out/robot1_B2.csv
"""
import argparse
import csv
import os
import time
import uuid
from datetime import datetime, timezone

from segb_bench import config as C
from segb_bench.metrics import write_csv
from segb_bench.replay import Capture, load_capture, replay


def wait_until(start_at: str | None) -> None:
    if not start_at:
        return
    target = datetime.fromisoformat(start_at)
    if target.tzinfo is None:
        target = target.astimezone()
    delay = (target - datetime.now(target.tzinfo)).total_seconds()
    if delay > 0:
        print(f"[{time.strftime('%H:%M:%S')}] waiting {delay:.1f}s until {start_at}")
        time.sleep(delay)


def run_ingest(args, cap: Capture) -> None:
    recs = []
    cumulative = 0
    for _ in range(args.repeats):
        _, cumulative = replay(
            C.BASE_URL, cap, setup="multi", mode=args.mode, robot_id=args.robot_id,
            run_id=args.run_id, data_prefixes=C.DATA_PREFIXES, gap_cap=C.GAP_CAP_S,
            rewrite=True, records=recs, cumulative0=cumulative,
        )
    write_csv(args.out, recs)
    print(f"[{args.robot_id}] wrote {len(recs)} records -> {args.out}")


def run_shared_context(args) -> None:
    """B3: resolve the SAME shared event from this robot, repeatedly.

    Requires semantic_log_generator installed and SEGB_API_URL set so the HTTP
    resolver is active. Every robot uses identical event evidence, so a correct
    backend must converge them onto one canonical IRI.
    """
    os.environ["SEGB_API_URL"] = C.BASE_URL
    from datetime import datetime, timezone

    from semantic_log_generator import SemanticSEGBLogger, build_http_shared_context_resolver_from_env

    resolver = build_http_shared_context_resolver_from_env()
    if resolver is None:
        raise SystemExit("Resolver inactive: set SEGB_API_URL / check backend.")

    logger = SemanticSEGBLogger(
        base_namespace=f"https://gsi.upm.es/segb/robots/{args.robot_id}/b3/",
        robot_id=args.robot_id, robot_name=args.robot_id,
        shared_event_resolver=resolver,
    )
    human = logger.register_human("maria", first_name="Maria")
    # Identical evidence across all robots -> must converge.
    observed_at = datetime(2026, 6, 3, 18, 0, 0, tzinfo=timezone.utc)

    rows = []
    for i in range(args.repeats):
        t0 = time.perf_counter()
        iri = logger.get_shared_event_uri(
            event_kind="spoken_utterance", observed_at=observed_at,
            subject=human, text="I need help", modality="speech",
        )
        rows.append({
            "robot_id": args.robot_id, "seq": i,
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            "shared_event_uri": str(iri),
        })
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[{args.robot_id}] resolved {len(rows)} times -> {args.out}")
    print(f"[{args.robot_id}] distinct IRIs: {len(set(r['shared_event_uri'] for r in rows))}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--robot-id", required=True)
    ap.add_argument("--mode", choices=["realistic", "saturation", "shared_context"], required=True)
    ap.add_argument("--start-at", default=None, help="ISO wall-clock start (NTP-synced)")
    ap.add_argument("--repeats", type=int, default=60)
    ap.add_argument("--run-id", default=uuid.uuid4().hex[:8])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    wait_until(args.start_at)

    if args.mode == "shared_context":
        run_shared_context(args)
    else:
        run_ingest(args, load_capture("capture.json"))


if __name__ == "__main__":
    main()
