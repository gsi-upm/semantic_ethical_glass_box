"""KG characterisation CLI (networkx structural stats + typed entity counts).

Run against the live backend, or against a saved TTL export:
  python kg_stats.py                 # from GET /events
  python kg_stats.py graph.ttl       # from a file

The triple/node/edge stats come from the /events Turtle dump (networkx).
Typed counts go through /query, whose results come back as Turtle, parsed with
sparql._parse_results.
"""
import json
import sys

import requests

from segb_bench import config as C
from segb_bench.kg import fetch_graph, graph_stats, load_graph_file
from segb_bench.sparql import _parse_results

# Typed counts aligned to the real data model (emotion recognition logs).
TYPED_COUNTS = {
    "logged_activities": f"SELECT (COUNT(?a) AS ?c) WHERE {{ ?a a <{C.NS['segb']}LoggedActivity> }}",
    "emotion_annotations": f"SELECT (COUNT(?ann) AS ?c) WHERE {{ ?ann <{C.NS['onyx']}hasEmotion> ?e }}",
    "messages": f"SELECT (COUNT(?m) AS ?c) WHERE {{ ?m a <{C.NS['schema']}Message> }}",
    "shared_events": f"SELECT (COUNT(DISTINCT ?ev) AS ?c) WHERE {{ ?ev a <{C.NS['schema']}Event> }}",
    "agents": f"SELECT (COUNT(DISTINCT ?ag) AS ?c) WHERE {{ ?act <{C.NS['prov']}wasAssociatedWith> ?ag }}",
}

# Shared events that bridge >= 2 robots (the multi-robot linking metric).
SHARED_EVENTS_BRIDGING = f"""
    SELECT (COUNT(DISTINCT ?ev) AS ?c) WHERE {{
        SELECT ?ev (COUNT(DISTINCT ?robot) AS ?nr) WHERE {{
            ?act <{C.NS['schema']}about> ?ev ;
                 <{C.NS['prov']}wasAssociatedWith> ?robot .
            ?ev a <{C.NS['schema']}Event> .
        }} GROUP BY ?ev HAVING (?nr >= 2)
    }}
"""


def _count(q: str) -> int:
    r = requests.get(f"{C.BASE_URL}/query", params={"query": q}, timeout=120)
    try:
        return int(str(_parse_results(r.text)[0]["c"]))
    except Exception:
        return -1


def main(path: str | None = None) -> None:
    g = load_graph_file(path) if path else fetch_graph(C.BASE_URL)
    stats = graph_stats(g)
    if not path:
        for name, q in TYPED_COUNTS.items():
            stats[name] = _count(q)
        stats["shared_events_bridging_2plus_robots"] = _count(SHARED_EVENTS_BRIDGING)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)