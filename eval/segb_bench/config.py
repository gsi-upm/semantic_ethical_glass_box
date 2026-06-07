"""Deployment-specific configuration.

EDIT the marked values once before running the suite. Everything that depends
on your concrete deployment or on the captured trace is centralised here so the
rest of the code stays generic.
"""

# --- Backend ----------------------------------------------------------------
# Auth is DISABLED in this deployment (SECRET_KEY unset), so no tokens are
# needed and every role is granted locally.
BASE_URL = "http://192.168.1.180:5000"   # real backend
PROXY_LISTEN = ("0.0.0.0", 8080)       # capture_proxy listen address
DEFAULT_USER = "bench_robot"

# --- Data namespaces (CALIBRATE from the captured trace) --------------------
# DATA_PREFIXES = the *instance* IRI namespaces that identify a concrete run.
# These are the ONLY IRIs the rewriter touches; vocabulary IRIs (onyx:, oro:,
# prov:, segb:, schema:, sosa:, oa:) must NOT appear here or they would be
# corrupted. Inspect one captured payload and copy the real prefixes.
DATA_PREFIXES = (
    "https://gsi.upm.es/segb/",
)
# For the SHARED-CONTEXT convergence test (B3) we must NOT rewrite the
# shared-event IRIs (all robots must point to the same event).
PRESERVE_PREFIXES_B3 = (
    "https://gsi.upm.es/segb/shared-events/",
)

# --- Ontology namespaces used by the report queries (CALIBRATE) -------------
# Confirm against the SEGB ontology reference and the Analysis Module queries.
NS = {
    "onyx": "http://www.gsi.upm.es/ontologies/onyx/ns#",
    "oa":   "http://www.w3.org/ns/oa#",
    "prov": "http://www.w3.org/ns/prov#",
    "segb": "http://www.gsi.upm.es/ontologies/segb/ns#",
    "schema": "http://schema.org/",
    "oro":  "http://kb.openrobots.org#",                    
    "sosa": "http://www.w3.org/ns/sosa/",
}

# --- Benchmark knobs --------------------------------------------------------
WARMUP_INSERTS = 10          # discarded before measuring (cold start / caches)
MIN_SAMPLES = 30             # measured ingestion samples per condition
SATURATION_SAMPLES = 200     # back-to-back inserts for throughput
GAP_CAP_S = 5.0              # cap real inter-log gaps in realistic mode
SCALABILITY_TARGET_TRIPLES = 50_000      # ceiling for the sweep
SCALABILITY_CHECKPOINT_TRIPLES = 5_000   # query suite + KG count each step
QUERY_REPEATS = 20           # repetitions per report query
