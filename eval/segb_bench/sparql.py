"""Report queries (GET /query) and query-latency timing.

The SEGB /query endpoint returns results as Turtle: each result row is a blank
node `[] a ns:Result ; ns:<var> <value>` under http://example.org/. We parse
that with rdflib. Report queries are aligned to the real logged data (emotion
recognition via onyx/oa terms), so they return real rows on the captured
interaction.
"""
from __future__ import annotations

import time

import requests
from rdflib import Graph, Namespace
from rdflib.namespace import RDF

from .config import NS

RES = Namespace("http://example.org/")  # SEGB /query result vocabulary

COUNT_TRIPLES = "SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }"

REPORTS = {
    "participants": f"""
        PREFIX oa: <{NS['oa']}>
        SELECT DISTINCT ?target WHERE {{ ?ann oa:hasTarget ?target }}
    """,
    "emotion_models": f"""
        PREFIX onyx: <{NS['onyx']}>
        SELECT DISTINCT ?model WHERE {{ ?act onyx:usesEmotionModel ?model }}
    """,
    "temporal_emotions": f"""
        PREFIX onyx: <{NS['onyx']}>
        PREFIX prov: <{NS['prov']}>
        PREFIX segb: <{NS['segb']}>
        SELECT ?t ?cat ?intensity WHERE {{
            ?act a onyx:EmotionAnalysis ;
                 prov:startedAtTime ?t ;
                 segb:producedEntityResult ?ann .
            ?ann onyx:hasEmotion ?e .
            ?e onyx:hasEmotionCategory ?cat ;
               onyx:hasEmotionIntensity ?intensity .
        }} ORDER BY ?t
    """,
    "extreme_emotions": f"""
        PREFIX onyx: <{NS['onyx']}>
        PREFIX segb: <{NS['segb']}>
        SELECT ?cat ?intensity WHERE {{
            ?act a onyx:EmotionAnalysis ; segb:producedEntityResult ?ann .
            ?ann onyx:hasEmotion ?e .
            ?e onyx:hasEmotionCategory ?cat ;
               onyx:hasEmotionIntensity ?intensity .
            FILTER(?intensity >= 0.75)
        }}
    """,
}


def _parse_results(ttl_text: str) -> list[dict]:
    """Parse the Turtle response: one blank node per row, ns:<var> per column."""
    g = Graph()
    g.parse(data=ttl_text, format="turtle")
    rows = []
    for s in g.subjects(RDF.type, RES.Result):
        row = {}
        for p, o in g.predicate_objects(s):
            if p == RDF.type:
                continue
            row[str(p).rsplit("/", 1)[-1]] = o
        rows.append(row)
    return rows


def run_query(base_url: str, q: str, timeout: int = 120):
    """Return (latency_ms, http_status, n_rows)."""
    t0 = time.perf_counter()
    r = requests.get(f"{base_url}/query", params={"query": q}, timeout=timeout)
    lat = (time.perf_counter() - t0) * 1000.0
    n = None
    try:
        n = len(_parse_results(r.text))
    except Exception:
        pass
    return lat, r.status_code, n


def count_kg(base_url: str) -> int:
    r = requests.get(f"{base_url}/query", params={"query": COUNT_TRIPLES}, timeout=120)
    try:
        return int(str(_parse_results(r.text)[0]["c"]))
    except Exception:
        return -1