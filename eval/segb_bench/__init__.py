"""SEGB quantitative evaluation harness.

Modules:
    config        deployment-specific constants (EDIT before running)
    metrics       latency records, percentiles, CSV I/O
    iri_rewriter  turn one real trace into N distinct-but-isomorphic traces
    replay        instrumented ingestion engine (POST /ttl)
    sparql        report queries + query-latency timing (GET /query)
    kg            networkx characterization of the KG (GET /events)
"""
