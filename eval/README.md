# SEGB — Evaluation: full reproducibility guide

This document describes, end to end, how the empirical evaluation of SEGB was
produced: the rationale behind every design decision, the exact steps to
reproduce it, and how the raw per-request logs become the final tables and
figure. It is intentionally detailed so that the evaluation can be re-run and
audited independently.

The paper reports a condensed subset; **this guide reports everything**,
including measurements that did not make it into the paper.

---

## 1. What we measure and why

SEGB has two performance-critical paths: **writing** logs into the Knowledge
Graph (KG) and **reading** them back as reports. The evaluation therefore targets
four questions:

1. How fast is a single robot's log ingestion? *(baseline latency)*
2. How does the system behave when several robots log at the same time?
   *(concurrency)*
3. Do ingestion and report latency degrade as the KG grows? *(scalability)*
4. What is the shape of the generated KG? *(structural characterisation)*

---

## 2. System under test

- **Server:** Storage + Analysis modules via Docker Compose on a single host,
  **one Uvicorn worker**, **Virtuoso co-located** on the same host.
- **Clients:** four identical PAL Robotics **TIAGo Head** robots; each runs the Log
  Generator Module as a dedicated ROS 2 node.
- **Network:** Wi-Fi.
- **Auth:** disabled for the evaluation (`SECRET_KEY` unset), so every endpoint is
  reachable without tokens.

This is the *default* deployment shipped with SEGB; we evaluate it as-is and
discuss its scaling levers in the limitations.

---

## 3. Methodology and design decisions

Every choice below was made to maximise realism while keeping the experiment
reproducible. Each decision is justified.

### 3.1 A single real interaction as the seed
**Decision:** drive every experiment from one real human–robot interaction
(~7 minutes), not from hand-written synthetic logs.
**Why:** the structure, vocabulary, and relationships of real logs are hard to
fake faithfully; using a real trace guarantees the data is representative.

### 3.2 Capturing with a transparent proxy (`capture_proxy.py`, `--no-forward`)
**Decision:** capture the interaction with a proxy placed between the robot and
the server, run with `--no-forward`.
**Why:** the proxy records every `POST /ttl` and its timestamp **without touching
the robot's code**. `--no-forward` means the capture does **not** pollute the real
SEGB graph (it returns a synthetic `200` so the robot's logger keeps working). The
result, `capture.json`, is the single source of truth for the whole evaluation.

### 3.3 Scaling by per-**interaction** relabelling (not per-message)
**Decision:** to grow the KG, replay the real trace many times; each replay gets
**one** fresh session identifier, rewriting only instance IRIs (robot, interaction
and shared-event namespaces) and leaving the ontology vocabulary untouched.
**Why:** re-sending the identical trace would be collapsed by the Storage Module's
redundancy handling and would not grow the graph. Relabelling per replay produces
distinct-but-faithful copies. Crucially the token is **per interaction, not per
message**: within one copy the human, robot and shared events keep a single
identity (as in the real interaction), so the copy stays internally linked. A
per-message token would shatter one human into dozens and distort both the graph
structure and the report row counts.

### 3.4 Two sending regimes: *time-preserving* vs *saturation*
**Decision:** replay either preserving the real inter-log gaps (*time-preserving*) or
back-to-back with no gaps (*saturation*).
**Why:** *time-preserving* reproduces the natural cadence of an interaction and therefore
the latency a robot actually experiences (including Wi-Fi link wake-up between
spaced logs). *saturation* removes the gaps so the connection stays warm,
exposing the server's raw service time and sustained throughput.

### 3.5 Single-robot vs multi-robot
**Decision:** measure one robot (baseline) and four robots logging concurrently.
The single-robot baseline is taken **on a robot**, not on a workstation.
**Why:** ingestion latency is the client→server→client round-trip, dominated by
network + server. Taking the 1-robot baseline on the same class of client and the
same Wi-Fi as the 4-robot run makes the 1↔4 comparison fair (apples to apples).
The four robots are launched with a common NTP-synchronised start time so they
truly contend at the single worker.

### 3.6 Network baseline
**Decision:** measure 200 round-trips to a near-empty endpoint (`/healthz/live`).
**Why:** to separate transport cost from server cost. It is **not subtracted** from
the results; it is a reference used to explain that the gap between *time-preserving*
(~49 ms) and *saturation* (~11 ms) is Wi-Fi wake-up, not server processing.

### 3.7 Warm-up and graph reset
**Decision:** discard the first ~10 insertions of each condition and reset the
graph between conditions.
**Why:** the first requests to a cold system (empty caches, new connections, cold
triple store) are unrepresentative; resetting gives every condition the same
clean starting point.

### 3.8 Metrics
- **Percentiles (p50/p95/p99), not the mean.** Latency over Wi-Fi is right-skewed;
  the median is the typical case and p95/p99 the tail. The mean is distorted by
  rare spikes.
- **Throughput is derived from latency** (`1000 / mean_latency` for one client;
  `× 4` for the four concurrent clients), because absolute per-request timestamps
  were not logged. It is an estimate, reported as such.

---

## 4. Step-by-step reproduction

Prerequisites: Python 3, `pip install rdflib networkx requests matplotlib`. Edit
`segb_bench/config.py` and set `BASE_URL`, `DATA_PREFIXES`
(`"https://gsi.upm.es/segb/"`) and the `NS` namespaces (note `segb`/`schema` use
`http`).

### Block 1–2 — Capture the real interaction

Preconditions: 
1. SEGB central server deployed according to the ReadTheDocs guide.
2. Have a ROS-based robot configured with the *semantic_log_generator* to produce and send TTL logs to the SEGB central server, and Use an intermediate host (e.g. a laptop) as a proxy to capture traffic from the robot to the SEGB central server. Launch this on the intermediate host: 

```bash
# point the robot's SEGB base_url at this proxy, run the interaction, Ctrl-C
python capture_proxy.py --no-forward          # on an intermediate host
```

We talked to the robot for around 7 min. During this time, robot was publishing to the proxy. Proxy's IP must be configured on the robot.

`test.ttl` is the joining TTL of every capture (it is not used and will not be generated during experiments execution, it was manually generated for inspection purposes)

```bash
python inspect_capture.py                      # -> 55 submissions, 2,691 triples
```



### Block 3 — Single client (from your PC) + network baseline
```bash
python network_baseline.py                     # Wi-Fi RTT
python bench_single.py                         # A1, A2, A3 (scalability sweep)
```
Outputs in `out/`: `single_A1.csv`, `single_A2.csv`, `single_A3_ingest.csv`,
`single_A3_query.csv`.


To send the scripts to the robot from the SEGB *root* directory (the ssh user and the IP of the robot must be changed):

```bash
scp -r eval user@10.0.0.11:~/
ssh user@10.0.0.11 "python3 -m pip install rdflib requests"
ssh user@10.0.0.11 "cd ~/eval && python3 -c 'from segb_bench.replay import load_capture; print(len(load_capture(\"capture.json\").payloads))'"

```

### Block 4 — Single robot baseline + 4 robots concurrent
Single-robot baseline (on robot1, resetting before each):
```bash
python3 -c "from segb_bench.replay import reset_graph; from segb_bench.config import BASE_URL; reset_graph(BASE_URL)"
python3 robot_agent.py --robot-id robot1 --mode realistic  --repeats 2 --out out/robot1_B1.csv
python3 -c "from segb_bench.replay import reset_graph; from segb_bench.config import BASE_URL; reset_graph(BASE_URL)"
python3 robot_agent.py --robot-id robot1 --mode saturation --repeats 5 --out out/robot1_B2.csv
```
Four robots concurrently, using the provided scripts for simplicity:
```bash
./launch_multi_robot_experiment.sh            # resets graph, computes common T0, launches all 4
./collect_results_multi_robot_experiment.sh   # scp the 4 CSVs and aggregate
```
`launch_multi_robot_experiment.sh` performs preflight checks, kills stale
processes, resets the graph from the first robot, computes a common UTC start time
(`T0 = now + 3 min`), and launches `robot_agent.py` on each robot with `setsid` so
they survive the SSH session and all fire at `T0`.

### Block 5 — KG characterisation
```bash
# load ONE real interaction unrewritten, then characterise
python3 -c "from segb_bench.replay import reset_graph, load_capture, replay; from segb_bench.config import BASE_URL; reset_graph(BASE_URL); replay(BASE_URL, load_capture('capture.json'), setup='single', mode='saturation', robot_id='ari41', run_id='kgchar', rewrite=False)"
python3 kg_stats.py
```

---

## 5. From raw data to tables

Every run writes **one CSV row per request**, with `latency_ms`, `ok`,
`cumulative_triples` and metadata. The aggregation is deterministic:

1. **Filter** to successful requests (`ok == True`).
2. **Latency tables:** take `latency_ms` and compute percentiles by linear
   interpolation (`metrics.percentile`). p50/p95/p99 are reported.
3. **Multi-robot aggregate:** the four robots' rows are **pooled into one set** and
   percentiles are computed over the pool — *not* an average of per-robot medians.
   We also report per-robot rows to show the load is balanced.
4. **Ingestion scalability:** `single_A3_ingest.csv` rows are binned by KG size and
   the p50 per bin is plotted. The x-axis uses the **Virtuoso** triple count
   recorded at each checkpoint, so ingestion and query series share one scale.
5. **Query scalability:** `bench_single.py` already records p50/p95 per report at
   each checkpoint (20 repetitions per query), written to `single_A3_query.csv`.
6. **KG characterisation:** `kg_stats.py` exports the whole graph via `GET /events`,
   builds a `networkx` graph for the structural stats, and runs `COUNT` queries for
   the typed entity counts (results parsed from the Turtle that `/query` returns).

---

## 6. Results — all tables

### 6.1 Network baseline (Wi-Fi, `/healthz/live`, n=200)
| metric | value (ms) |
|---|--:|
| mean | 15.8 |
| p50 | 8.7 |
| p95 | 50.7 |
| p99 | 67.8 |
| min / max | 4.6 / 97.6 |
| stdev | 15.3 |

The low median (8.7 ms) is the floor of any round-trip; the wide tail (p95 50.7 ms)
is Wi-Fi jitter.

### 6.2 Single robot — real hardware (paper)
| Condition | n | mean | p50 | p95 | p99 | errors |
|---|--:|--:|--:|--:|--:|--:|
| time-preserving | 110 | 55.2 | 48.7 | 112.1 | 150.0 | 0 |
| saturation | 275 | 11.5 | 11.0 | 14.6 | 28.1 | 0 |

Saturation (~11 ms) ≈ server service time (warm pipe). time-preserving (~49 ms) adds Wi-Fi
wake-up between spaced logs.

### 6.3 Single client — workstation reference (not in paper)
| Condition | n | mean | p50 | p95 | p99 | max |
|---|--:|--:|--:|--:|--:|--:|
| A1 time-preserving (PC) | 55 | 76.4 | 82.8 | 150.4 | 252.6 | 308.9 |
| A2 saturation (PC) | 220 | 24.6 | 15.8 | 59.3 | 96.6 | 216.3 |

Included for transparency. The workstation client is noisier than the robot;
the robot numbers (6.2) are the ones used in the paper.

### 6.4 Four robots, saturation — per robot and pooled (paper)
| Robot | n | mean | p50 | p95 | p99 |
|---|--:|--:|--:|--:|--:|
| robot1 | 275 | 22.8 | 22.0 | 33.0 | 55.6 |
| robot2 | 275 | 23.5 | 22.7 | 32.8 | 53.1 |
| robot3 | 275 | 23.5 | 22.6 | 34.4 | 53.6 |
| robot4 | 275 | 23.3 | 22.8 | 33.2 | 53.5 |
| **pooled** | **1100** | **23.3** | **22.6** | **33.4** | **55.5** |

0 errors; per-robot medians within 21.97–22.82 ms (balanced). Estimated aggregate
throughput ≈ 172 logs/s (vs ≈ 87 logs/s for one robot).

### 6.5 Ingestion scalability (single client, saturation)
KG size from the Virtuoso checkpoints; p50 per bin.

| KG (k triples) | 10.9 | 16.1 | 21.3 | 26.5 | 31.7 | 36.9 | 42.0 | 44.6 | 49.8 | 55.0 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| p50 (ms) | 13.7 | 17.6 | 13.6 | 12.4 | 11.7 | 13.9 | 18.1 | 14.9 | 14.0 | 13.6 |

Overall (all inserts): n=1045, p50 13.8, p95 57.1, max 245.8 ms. **Flat** — no
degradation as the KG grows.

### 6.6 Query scalability (single client) — p50 / p95 (ms) per report
| KG triples | participants | emotion_models | temporal_emotions | extreme_emotions |
|--:|--|--|--|--|
| 10931 | 12.8 / 52.1 | 12.6 / 69.1 | 19.1 / 75.1 | 15.2 / 50.9 |
| 16115 | 13.8 / 53.7 | 12.0 / 42.8 | 56.9 / 1095.0\* | 24.0 / 68.3 |
| 21299 | 11.8 / 70.9 | 9.4 / 59.1 | 24.3 / 60.0 | 24.9 / 74.0 |
| 26483 | 10.5 / 25.7 | 9.5 / 14.6 | 21.0 / 29.9 | 18.4 / 33.9 |
| 31667 | 11.9 / 56.6 | 10.0 / 40.2 | 25.3 / 61.1 | 24.3 / 70.5 |
| 36851 | 13.4 / 27.3 | 11.0 / 41.3 | 29.6 / 89.2 | 45.5 / 93.3 |
| 42035 | 14.7 / 37.9 | 11.8 / 49.7 | 33.7 / 57.9 | 23.5 / 47.7 |
| 44627 | 12.7 / 35.2 | 11.3 / 37.7 | 40.6 / 86.6 | 37.5 / 113.8 |
| 49811 | 13.0 / 44.5 | 10.2 / 29.0 | 35.6 / 92.1 | 28.9 / 53.9 |
| 54995 | 12.7 / 35.7 | 10.6 / 32.3 | 37.2 / 58.0 | 37.0 / 53.0 |

Row counts grow with size: `participants` 2→19, `emotion_models` = 1 (a vocabulary
IRI, constant), `temporal_emotions` / `extreme_emotions` 12→114.
\* Transient one-off spike (GC/triple-store); excluded from the figure.

In the figure, `temporal_emotions` is shown as the **heavy** report and
`participants` as the **light** report.

### 6.7 Knowledge graph (one real interaction)
| Property | Value |
|---|--:|
| Triples (emitted → stored) | 2,691 → 2,592 |
| Nodes / Edges | 755 / 2,592 |
| Connected components | 1 (755 nodes) |
| Avg. degree / density | 6.87 / 0.0046 |
| Logged activities | 55 |
| Emotion annotations | 6 |
| Messages | 23 |
| Shared events | 30 |
| Agents | 2 |

The single connected component is the key result: all logs are integrated into one
coherent graph. The 2,691→2,592 reduction is the Storage Module merging repeated
declarations (same human/robot/procedures), evidencing its redundancy handling.
*(`agents = 2`: the robot plus an `unknown_robot` placeholder emitted by the motion
node; harmless, fixable at the source.)*

### 6.8 Figure
`scalability.pdf` / `scalability.png`: p50 latency vs KG size for ingestion, the
light SPARQL query and the heavy SPARQL query, all on the Virtuoso triple-count
axis. Ingestion and the light query stay flat; the heavy query grows sub-linearly.

---

## 7. Limitations

1. **Logging detail.** What is published to SEGB depends on the level of detail a
   user configures in `semantic_log_generator`, which changes the number of triples
   per submission and hence the processing time. These experiments used a high
   level of detail in order to test the worst cases.
2. **Hardware and network.** Results depend on the hardware of the robot clients
   and the central server (here, a single Uvicorn worker with a co-located triple
   store) and on network conditions (Wi-Fi). Other infrastructure (more workers, a wired link, a host with higher hardware resources...) would shift the numbers.
3. **Synthetic scaling.** Large graphs are one real interaction replayed at scale:
   structurally faithful but may be limited in behavioural diversity.
4. **Throughput is estimated** from latency, as absolute per-request timestamps
   were not recorded.
