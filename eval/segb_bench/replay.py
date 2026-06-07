"""Instrumented ingestion engine: replays a captured trace against POST /ttl."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
import uuid

import requests
from rdflib import Graph

from .iri_rewriter import rewrite_session
from .metrics import IngestRecord


@dataclass
class Capture:
    payloads: list  # [{"ts": float, "ttl": str, "user": str}, ...]


def load_capture(path) -> Capture:
    with open(path) as fh:
        data = json.load(fh)
    return Capture(payloads=data["payloads"])


def count_triples(ttl: str) -> int:
    g = Graph()
    g.parse(data=ttl, format="turtle")
    return len(g)


def real_gaps(cap: Capture) -> list[float]:
    """Inter-arrival gaps derived from the real capture timestamps."""
    ts = [p["ts"] for p in cap.payloads]
    return [0.0] + [max(0.0, ts[i] - ts[i - 1]) for i in range(1, len(ts))]


def insert_ttl(base_url: str, ttl: str, user: str, timeout: int = 30):
    t0 = time.perf_counter()
    try:
        r = requests.post(
            f"{base_url}/ttl",
            json={"ttl_content": ttl, "user": user},
            timeout=timeout,
        )
        return (time.perf_counter() - t0) * 1000.0, r.status_code, r.status_code < 400
    except requests.RequestException:
        return (time.perf_counter() - t0) * 1000.0, -1, False



def replay(
    base_url: str,
    cap: Capture,
    *,
    setup: str,
    mode: str,
    robot_id: str,
    run_id: str,
    data_prefixes=(),
    preserve_prefixes=(),
    gap_cap: float = 5.0,
    rewrite: bool = False,
    records: list | None = None,
    cumulative0: int = 0,
):

    """
        Replay one pass of the captured trace.

        mode == "realistic"  -> sleep the real inter-log gaps (online latency)
        mode == "saturation" -> back-to-back, no gaps (service time / throughput)
        rewrite == True       -> mint a fresh distinct session for this pass
    """
    
    records = records if records is not None else []
    gaps = real_gaps(cap) if mode == "realistic" else [0.0] * len(cap.payloads)
    cumulative = cumulative0
    session_token = uuid.uuid4().hex[:12] if rewrite else None

    for seq, (p, gap) in enumerate(zip(cap.payloads, gaps)):
        if mode == "realistic" and gap > 0:
            time.sleep(min(gap, gap_cap))
        ttl = p["ttl"]
        if rewrite:
            ttl, _ = rewrite_session(ttl, data_prefixes, preserve_prefixes,
                                        session_token=session_token)
            # <
        n = count_triples(ttl)
        lat, status, ok = insert_ttl(base_url, ttl, p.get("user") or robot_id)
        records.append(
            IngestRecord(
                run_id=run_id, setup=setup, mode=mode, robot_id=robot_id,
                seq=seq, n_triples=n, payload_bytes=len(ttl.encode("utf-8")),
                cumulative_triples=cumulative, latency_ms=lat,
                http_status=status, ok=ok,
            )
        )
        if ok:
            cumulative += n
    return records, cumulative


def reset_graph(base_url: str, user: str = "operator") -> None:
    """Wipe the KG between conditions (admin; allowed because auth is off)."""
    requests.post(f"{base_url}/ttl/delete_all", json={"user": user}, timeout=60)
