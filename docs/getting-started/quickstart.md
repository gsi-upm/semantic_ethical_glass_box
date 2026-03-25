# Quickstart

This guide gives you the shortest complete SEGB run. You will deploy the backend and frontend, load the UC-02 report-ready dataset,
and verify that the reports and graph explorer show real interaction data. The underlying script can be found in the GitHub repo at
`examples/simulations/run_use_case_02_report_ready_dataset.py`.

## What You Will Get

After completing this guide, you will have SEGB deployed and some demo data ingested into the Knowledge Graph (KG).
We use UC-02, a simulation-like script that generates and ingests TTL into SEGB. UC-02 is designed to simulate a short but realistic interaction in which a human, Maria, and a robot, ARI, interact as follows:

1. Maria asks ARI for a piece of news that might cheer her up.
2. ARI replies with an exam-related headline, which has the opposite effect on Maria because she is afraid of exams.
3. An emotion-analysis process run by ARI detects anxiety in Maria.
4. ARI apologizes, switches strategy, and replies with positive animal-rescue news.
5. Maria finally feels happy after reading that last piece of news.

After the import, you can inspect three concrete artifacts:

- Populated reports such as participants, temporal emotions, or conversation history, created from the information in
the KG.
- A connected Knowledge Graph linking humans, robots, activities, messages, model usage, and emotions. You can inspect
this KG graphically and through SPARQL queries.
- Query results and graph exports in Turtle format, which let you inspect the same data as text.

### Example Knowledge Graph

![UC-02 Knowledge Graph](../assets/screenshots/ui-kg-graph.png)

### Example Reports

![UC-02 Reports Dashboard](../assets/screenshots/ui-reports.png)

## Example Query Result In Turtle

On `http://localhost:8080/query`, the query workbench shows the result in two ways: a `SELECT Result Table` for quick
inspection and a `Raw Turtle Result` card with the same output serialized as Turtle. A typical Turtle result for the
example query later in this guide looks like this:

```turtle
@prefix ns: <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

[] a ns:Result ;
    ns:robotName "robot_ari1" ;
    ns:senderName "Maria"@en ;
    ns:t "2026-03-25T12:24:49.574054+00:00"^^xsd:dateTime ;
    ns:text "ARI, can you show me some news to cheer me up?"@en .

[] a ns:Result ;
    ns:robotName "robot_ari1" ;
    ns:senderName "robot_ari1" ;
    ns:t "2026-03-25T12:24:59.574054+00:00"^^xsd:dateTime ;
    ns:text "Here is one headline: many students are anxious because an important exam is coming soon."@en .

[] a ns:Result ;
    ns:robotName "robot_ari1" ;
    ns:senderName "robot_ari1" ;
    ns:t "2026-03-25T12:26:49.574054+00:00"^^xsd:dateTime ;
    ns:text "I am sorry, Maria. That exam news was not a good choice right now."@en .
```

The exact timestamps and blank-node identifiers will differ on your machine, but the result should be non-empty and
should show the message timeline from the demo dataset.

## Mental Model First

This guide uses UC-02, a simulation-like script that generates and ingests TTL into SEGB for demo purposes. It
populates the parts of the graph that make SEGB reports easy to understand: participants, messages, model usage,
emotions, and robot state.


## Before You Start

You need:

- Docker Engine and Docker Compose v2
- free host ports `5000`, `8080`, `8890`, and `1111`
- Python `3.10+`


If you do not yet have a local checkout, clone the repository and enter it now:

```bash
git clone https://github.com/gsi-upm/semantic_ethical_glass_box.git
cd semantic_ethical_glass_box
```

All commands below assume you are working from the repository root.

## Step 1: Create The Local Environment File

Copy the example file and set the Virtuoso password:

```bash
cp .env.example .env
```

Set at least this value:

```env
VIRTUOSO_PASSWORD=change-this-password
```

Only `VIRTUOSO_PASSWORD` must be set for the first run. The value is used only when the `virtuoso_data` volume is
created for the first time, so changing it later does not update an existing database password. 

To keep the first run simple, it is recommended that you keep authentication disabled by leaving `SECRET_KEY` empty in
`.env`.


## Step 2: Start The Centralized Stack

Run:

```bash
docker compose -f docker-compose.yaml pull
docker compose -f docker-compose.yaml up -d
```

This compose file starts the published backend and frontend images from GHCR. 

## Step 3: Wait For The Backend To Become Ready

Run:

```bash
curl -s http://localhost:5000/healthz/live
curl -s http://localhost:5000/healthz/ready
```

You want `{"live": true}` and `{"ready": true, "virtuoso": true}`. If readiness stays `false`, stop here and check
[Centralized Deployment](../operations/centralized-deployment.md).

## Step 4: Create A Small Python Environment For The Demo Loader

The next step uses one of the simulation scripts that ships with the repository. Create a small local environment for
it:

```bash
python3 -m venv .segb_env
./.segb_env/bin/python -m pip install -U pip
./.segb_env/bin/python -m pip install -e packages/semantic_log_generator
./.segb_env/bin/python -m pip install pydantic
```

`pydantic` is needed because some simulation flows validate backend JSON responses with typed contracts, but it is not
part of the SEGB toolkit.

## Step 5: Load The UC-02 Demo Dataset

Let us load the UC-02 demo dataset. The script clears the configured graph before inserting new data, so treat it as a
resettable demo loader rather than as an additive import.

If authentication is disabled (recommended):

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --no-print-ttl
```

If authentication is enabled, use an `admin` token:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --token "<admin_jwt>" \
  --no-print-ttl
```

If you chose protected mode and still need a token, use
[Authentication and JWT](../operations/authentication-and-jwt.md) first and come back when you have an `admin` token.

## Step 6: Open The UI

Open `http://localhost:8080/reports`, `http://localhost:8080/kg-graph`, and `http://localhost:8080/query`.

If authentication is enabled, open `http://localhost:8080/session` first and paste a token with the `admin` or `auditor` role.

### Example SPARQL Query

After Step 6, open `http://localhost:8080/query` and run this read-only query to inspect the message timeline produced
by UC-02:

```sparql
PREFIX segb: <http://www.gsi.upm.es/ontologies/segb/ns#>
PREFIX schema: <http://schema.org/>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX oro: <http://kb.openrobots.org#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?t ?robotName ?senderName ?text
WHERE {
  ?message a schema:Message ;
           schema:text ?text ;
           prov:wasGeneratedBy ?activity .

  ?activity a segb:LoggedActivity ;
            segb:wasPerformedBy ?robot .

  ?robot a oro:Robot .
  OPTIONAL { ?activity prov:startedAtTime ?t }
  OPTIONAL { ?robot rdfs:label ?robotLabel }
  BIND(COALESCE(?robotLabel, REPLACE(STR(?robot), "^.*[/#]", "")) AS ?robotName)

  OPTIONAL { ?message schema:sender ?sender }
  OPTIONAL { ?sender foaf:firstName ?senderFirstName }
  OPTIONAL { ?sender rdfs:label ?senderLabel }
  BIND(COALESCE(?senderFirstName, ?senderLabel, REPLACE(STR(?sender), "^.*[/#]", "")) AS ?senderName)
}
ORDER BY ?t ?robotName
LIMIT 20
```

When you run this query in `/query`, the page should show non-empty rows in the `SELECT Result Table` and the same
result serialized in the `Raw Turtle Result` card. The raw Turtle output should look similar to the example shown in
[Example Query Result In Turtle](#example-query-result-in-turtle), although your exact timestamps and blank-node
identifiers will differ.

## Step 7: Verify That The Run Is Meaningful

On `/reports`, you should see actual content such as
participants, conversation history, model usage, emotions, or robot state. On `/kg-graph`, you should see connected
nodes rather than an empty canvas, with links between robots, humans, activities, messages, and other entities from the
demo dataset. On `/query`, the example query on this page should return non-empty rows. Check
[Explore the Web UI](../guides/explore-the-web-ui.md) for a better understanding of the UI pages. The backend should
also export non-empty Turtle:

If authentication is disabled (recommended):

```bash
curl -s http://localhost:5000/events | head -n 20
```

If authentication is enabled:

```bash
curl -s http://localhost:5000/events \
  -H "Authorization: Bearer <auditor_or_admin_jwt>" | head -n 20
```

If that export is non-empty and the UI pages are populated, you have completed the full SEGB loop.

## If Something Does Not Work

- `ready=false` on `/healthz/ready`: the backend cannot talk to Virtuoso yet. Check `docker compose -f docker-compose.yaml logs -f amor-segb amor-segb-virtuoso`.
- `401/403` while loading the demo dataset: you enabled auth, but the script is missing a valid `admin` token.
- `/reports` is empty: run the dataset loader again and refresh `/reports`.
- `Connection refused`: check whether the compose stack is still running with `docker compose -f docker-compose.yaml ps`.

## Next Steps

Now that you have a working stack, read [Core Concepts and Roles](core-concepts-and-roles.md), then continue with
[Publish Your First Log](../guides/publish-your-first-log.md) and
[Explore the Web UI](../guides/explore-the-web-ui.md).
