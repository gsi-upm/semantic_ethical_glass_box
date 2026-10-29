# Centralized Deployment

## When To Use This Page

Use this page when you want to operate the full SEGB stack in Docker.

If your goal is simply to get SEGB running once and see data in the UI, start with
[Quickstart](../getting-started/quickstart.md). This page is for:

- choosing the right compose file
- understanding `.env`
- checking health
- stopping or resetting the stack safely

## What Gets Deployed

The centralized stack includes:

- the backend API
- the Virtuoso Knowledge Graph
- the SEGB web UI

## Before You Start

You need:

- Docker Engine `24.0+`
- Docker Compose plugin `v2.20+`
- free host ports `5000`, `8080`, `8890`, and `1111`
- to run commands from the repository root

Version check:

```bash
docker version --format '{{.Server.Version}}'
docker compose version
```

## Step 1: Choose Your Stack Mode

SEGB ships with two compose files.

### Production-Like Compose

Use this when you want the published images from GHCR:

- `docker-compose.yaml`

This is the best choice for demos, quick evaluation, and reproducible local runs. The web UI runs on port `8080` and set the API server on port `5000`

### Development Compose

Use this when you are editing the software itself and want hot reload:

- `docker-compose.dev.yml`

This mode runs the frontend on port `5173` and also set the API server on port `5000`

## Step 2: Create `.env`

Copy the example file:

```bash
cp .env.example .env
```

Set the required passwords:

```env
VIRTUOSO_PASSWORD=change-this-password
VIRTUOSO_READER_USER=segb_reader
VIRTUOSO_READER_PASSWORD=change-this-reader-password
```

Important details:

- this value initializes the Virtuoso DBA password only when the `virtuoso_data` volume is created for the first time,
- if the volume already exists, changing `VIRTUOSO_PASSWORD` later does not change the stored database password,
- if you really need a fresh password, you must recreate the volume with a destructive reset.

Use distinct passwords for the writer and reader. Both Compose files run `segb-query-reader-init` before the backend.
This job uses the pinned Virtuoso image's `isql` and
[`provision-query-reader.sh`](../../apps/backend/virtuoso/provision-query-reader.sh) to create the reader or rotate its
password. The backend starts only if provisioning succeeds. Keep the script alongside the Compose file when deploying.
For an existing volume, use the database's current DBA password; provisioning does not reset it or remove data.

Optional secure mode:

```env
SECRET_KEY=replace-with-a-long-random-secret
```

If you set `SECRET_KEY`, SEGB enables JWT authentication and enforces roles. If you leave it empty, local auth is
disabled.

## Step 3: Start The Stack

Production-like stack:

```bash
docker compose -f docker-compose.yaml pull
docker compose -f docker-compose.yaml up -d
```

Development stack:

```bash
docker compose -f docker-compose.dev.yml up --build -d
```

## Query Account Isolation

`GET /query` uses a separate HTTP Digest session authenticated as `VIRTUOSO_READER_USER`. Writes, deletion, `/log`,
`/history`, and other audit reads continue to use `VIRTUOSO_USER` / `VIRTUOSO_PASSWORD` (default user `dba`).
`VIRTUOSO_GRAPH_URI` defaults to `http://segb/events`; `VIRTUOSO_AUDIT_GRAPH_URI` defaults to `http://segb/audit`.
These must be different. The reader credentials are required even when API JWT authentication is disabled.

Provisioning resets all of the reader's graph grants, denies default access to both public and private graphs, and
grants only read permission (mask `1`) on the events graph. It removes extra direct roles and checks the full inherited
role list in `SYS_ROLE_GRANTS`: only `SPARQL_SELECT` and its built-in `SPARQL_LOAD_SERVICE_DATA` role are allowed.
`SPARQL_UPDATE`, `SPARQL_SPONGE`, DBA, and other inherited roles cause refusal. Before changing an existing account,
provisioning also refuses **every direct SQL object grant** recorded in `SYS_GRANTS`, including table/column reads,
writes, and procedure `EXECUTE`. Graph permissions do not constrain definer-rights routines. Use a fresh dedicated
account, or have the DBA review and explicitly `REVOKE` these grants before retrying. Refusal leaves the old grants
and password intact; it prevents the account from being accepted as the API reader rather than silently removing
privileges from a potentially shared account. Provisioning does not edit system catalogs directly.

Graph permissions do not constrain SQL: a SPARQL query can call any SQL routine its account may `EXECUTE`
(`sql:ROUTINE()`), and routines run with their owner's rights. On the pinned image the reader inherits roughly 250
SQL grants from `SPARQL_SELECT`, its nested roles, and `PUBLIC`. These are Virtuoso's own SPARQL support routines
and views. A real-database regression shows that any further `EXECUTE` grant to `PUBLIC` or `SPARQL_SELECT` on a
routine that writes a table lets the reader's SPARQL query run it. So the effective set is checked, not assumed:

- [`reader-sql-policy.manifest`](../../apps/backend/virtuoso/reader-sql-policy.manifest) lists every SQL grant the
  reader may hold (its own, inherited from roles, `PUBLIC`, and `nobody`), the role names, and an MD5 of each granted
  routine's stored body. It was generated on a fresh pinned image and reviewed; it is the only trusted input.
- Provisioning refuses an existing account with direct grants, then requires the listing Virtuoso computes to equal
  the manifest. A new grant, an extra role (for example `SPARQL_SELECT_FED`), or a routine whose body changed
  (including a built-in that was re-created) fails with a diff. On success it stores a digest of the verified
  listing in `DB.DBA.SEGB_QUERY_READER_POLICY`; any failed run deletes the stored digest first.
- The backend asks `DB.DBA.SEGB_QUERY_READER_SQL_POLICY_DRIFT` (called with the writer account, no `EXECUTE` grant to
  the reader or `PUBLIC`) whether the live listing still equals the stored digest, at startup and again before a
  user query or readiness ping once `VIRTUOSO_READER_POLICY_RECHECK_SECONDS` (default 30) have passed. A grant added
  or a routine replaced later, a missing digest, or a failing check refuse the query; on drift the reader session is
  dropped until the backend restarts against a re-provisioned account. The stored digest is the one reported with the
  listing that matched the manifest, so a concurrent change cannot become the trusted baseline. The listing also
  contains `OWNS|...` lines for tables and procedures under the reader's own schema, because owner rights need no grant.

Limits: the manifest is tied to the pinned image build (isql reported Virtuoso 07.20.3242 for `7.2.16`). Another
build may legitimately change the listing; provisioning then fails closed and an operator must review the diff and
regenerate the manifest on a disposable database with `VIRTUOSO_PRINT_READER_POLICY=1`. The built-in routines
listed in the manifest are trusted as shipped; built-ins without a stored body are only detected when replaced
(the replacement gains a stored body). A DBA can still forge the stored digest, which is outside this threat model.

Accepted residual risks, observed on the pinned image with the reader's own identity: the approved routines include
`DB.DBA.RDF_OBJ_ADD`, which a reader's SPARQL call can use to add rows to `DB.DBA.RDF_OBJ` (storage growth, no graph
change), and `SPARUL_LOAD_SERVICE_DATA`, which Virtuoso denies with `SR619` when the reader has no write permission on
the target graph. `SPARQL_SD_PROBE` and `SPARQL_REXEC_TO_ARRAY` are approved too and were not shown to change a graph or
to bypass the `SERVICE` denial, but `SPARQL_REXEC_TO_ARRAY` was not exercised to a conclusion; treat both as trusted
as shipped. The lexical filter in the API rejects explicit `sql:` calls, and it should stay.

**Native SQL access is not graph-isolated.** Graph permissions are applied by the SPARQL compiler. On the pinned
image the reader can read audit rows with a plain `select ... from DB.DBA.RDF_QUAD` over `isql` or ODBC (the manifest
approves `SELECT` on that table, as Virtuoso grants it to `SPARQL_SELECT`), and a regression records this. The reader's
credentials therefore protect `GET /query` only while they stay inside the backend: do not publish port 1111, and keep
them out of any client. This is the same boundary described under raw SQL below.

Virtuoso also applies public permissions granted to `nobody`. Provisioning checks graph permissions and fails if audit
is accessible or events has more than read access. It does not change shared `nobody` grants or role definitions.
An operator must review incompatible public grants or a modified `SPARQL_SELECT` role before retrying. See OpenLink's
[graph permissions](https://docs.openlinksw.com/virtuoso/fn_rdf_graph_user_perms_get/),
[default permissions](https://docs.openlinksw.com/virtuoso/rdfgraphsecurityunddefperm/), and
[role inheritance tables](https://docs.openlinksw.com/virtuoso/usersystables/).

The backend refuses missing credentials, the writer/DBA identity, failed reader authentication, unsafe graph grants,
or a successful write probe; it never retries a user query as DBA. Startup checks inherited update, sponge and DBA
roles, SQL privilege drift (see above), audit permissions even if audit has no triples, and that events is
read-only. Startup fails if the drift function is missing, fails, or returns an unusable result. The writer account
must be able to execute it and `DB.DBA.RDF_GRAPH_USER_PERMS_GET` for these fixed administrative checks. Restrict privilege changes to trusted operators and rerun provisioning after
any grant changes.

The events dataset pin and lexical query checks remain required parts of the API boundary. Virtuoso 7.2.16 can expose
graph **names** through an unpinned `SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }` optimization even when graph
triples are inaccessible. The backend pins both default and named datasets to events. Do not expose database
credentials or the database service directly to API clients.

This metadata limitation reveals graph existence/names, not just triples: the reader credentials alone do **not**
satisfy a requirement to hide all audit metadata. The regression explicitly records the unpinned name leak and
checks that `/query` hides those names even with the lexical filter disabled. Local triple/count isolation and the
documented `/query` boundary are narrower guarantees than complete secrecy for direct database clients.

Keep the `SERVICE` rejection as well. A federated query runs at the remote endpoint under that endpoint's identity,
so the local reader's graph ACLs do not apply to it. On the pinned image Virtuoso itself refuses `SERVICE` for an
account that only holds `SPARQL_SELECT` (HTTP 500, `SQ070` on `DB.DBA.SPARQL_SINV_2` or `SR186` on
`DB.DBA.SPARQL_SINV_IMP`); the real regression records that, plus the control that the same query returns audit rows
once the reader also holds `SPARQL_SELECT_FED` and the remote identity can read audit. The privilege check above
rejects that role, so federation stays closed at the database as well as in the API. Do not grant the reader
`SPARQL_SELECT_FED` or `SELECT` on the `SPARQL_SINV` objects.

Raw SQL is another distinct boundary: OpenLink documents that graph ACLs are applied by the SPARQL compiler,
and its additional `SPARQL_SELECT_RAW` protection is for Virtuoso 7.5 or higher, not an assumption we can make for
the pinned 7.2.16 image. Direct grants are therefore refused rather than relying on graph ACLs to constrain SQL.
The regressions include raw audit row/count reads through `bif:exec`; those are not a verification of native
ODBC/isql access using the reader credentials. See [Graph-Level Security and SQL](https://docs.openlinksw.com/virtuoso/rdfgraphsecuritylevelrow/).

To rotate the reader password or change graph names, update `.env`, stop the backend, rerun provisioning, and recreate
the backend so its sessions use the new settings (substitute the development Compose file when applicable):

```bash
docker compose -f docker-compose.yaml stop segb
docker compose -f docker-compose.yaml run --rm segb-query-reader-init
docker compose -f docker-compose.yaml up -d --force-recreate segb
```

For a backend outside Compose, run the same script on a trusted host with `isql` installed, against the intended
Virtuoso SQL port, before starting the API. Supply secrets through your deployment's environment/secret manager:

```bash
# Export VIRTUOSO_ADMIN_PASSWORD and VIRTUOSO_READER_PASSWORD securely first.
export VIRTUOSO_ADMIN_USER=dba
export VIRTUOSO_ISQL_ADDRESS=your-virtuoso-host:1111
export VIRTUOSO_READER_USER=segb_reader
export VIRTUOSO_GRAPH_URI=http://segb/events
export VIRTUOSO_AUDIT_GRAPH_URI=http://segb/audit
sh apps/backend/virtuoso/provision-query-reader.sh
```

With Compose and an external Virtuoso, set `VIRTUOSO_ENDPOINT` and `VIRTUOSO_ISQL_ADDRESS` (its SQL port) in `.env`:
`segb-query-reader-init` then provisions that server and never the bundled `segb-virtuoso`. Compose still makes the init
job and the backend depend on the bundled container, so `docker compose up` creates it (and publishes ports 1111 and
8890, which can clash with a local server). To avoid that, use an override file that removes it (the snippet needs Compose 2.24.4 or later) and pass it as a second
`-f` to every Compose command, including the rotation commands below, because an explicit `-f docker-compose.yaml`
does not load `docker-compose.override.yml` by itself:

```yaml
# docker-compose.external-virtuoso.yml
services:
  segb-virtuoso:
    profiles: ["bundled-virtuoso"]
  segb-query-reader-init:
    depends_on: !reset []
  segb:
    depends_on: !override
      segb-query-reader-init:
        condition: service_completed_successfully
```

```bash
docker compose -f docker-compose.yaml -f docker-compose.external-virtuoso.yml up -d
```

Configure the API's `VIRTUOSO_ENDPOINT` to the corresponding authenticated `/sparql-auth` endpoint and set both writer
and reader credentials. A failed provisioning command is a deployment failure; do not substitute writer credentials
for reader credentials. The isolated real-database verification command is documented in [Tests](../../tests/README.md).

## Step 4: Check Health

Run:

```bash
curl -s http://localhost:5000/healthz/live
curl -s http://localhost:5000/healthz/ready
curl -s http://localhost:5000/auth/mode
```

Expected outputs:

- `{"live": true}`
- `{"ready": true, "virtuoso": true}`
- `{"auth_enabled": false}` or `{"auth_enabled": true}`

## Step 5: Load Data If You Want A Useful First Inspection

The stack can be healthy and still look empty. To make the UI meaningful, load some data.

The fastest option is the report-ready demo dataset used in [Quickstart](../getting-started/quickstart.md).

## Step 6: Open The Services

Typical URLs:

- Backend OpenAPI docs: `http://localhost:5000/docs`
- UI in production-like mode: `http://localhost:8080`
- UI in development mode: `http://localhost:5173`

## Stop And Reset

### Stop The Stack

Production-like mode:

```bash
docker compose -f docker-compose.yaml down
```

Development mode:

```bash
docker compose -f docker-compose.dev.yml down
```

### Reset Only The Graph Content

If auth is disabled:

```bash
curl -X POST http://localhost:5000/ttl/delete_all \
  -H "Content-Type: application/json" \
  -d '{"user":"operator"}'
```

If auth is enabled:

```bash
curl -X POST http://localhost:5000/ttl/delete_all \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin_jwt>" \
  -d '{"user":"operator"}'
```

This removes graph data but keeps the Virtuoso volume.

### Reset The Entire Virtuoso Volume

Production-like mode:

```bash
docker compose -f docker-compose.yaml down -v
```

This is destructive. It deletes the persisted database volume.

## Upgrading From 1.1.x

Version `1.2.0` renamed the stack: the services are now `segb` and `segb-virtuoso`, the backend image is
`ghcr.io/gsi-upm/semantic_ethical_glass_box/segb`, and the default event graph is `http://segb/events`.

A 1.1.x deployment keeps its triples in the graph it used before, which has a different name, so after upgrading the new
default graph looks empty. To keep reading the existing data, find the old graph name and set it explicitly in `.env`:

```sparql
SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }
```

```bash
VIRTUOSO_GRAPH_URI=<the graph name returned by the query>
```

Version `1.2.0` also adds an `audit_dumps` volume to the backend (large dumps of deleted graphs; see
[Audit Vocabulary](../reference/audit-vocabulary.md)). `docker compose up` creates it; include it in your backups.

Also update anything that referred to the old container, service or image names (scripts, `docker compose logs` calls,
reverse-proxy targets).

## Common Problems

- backend not ready: check `docker compose -f docker-compose.yaml logs -f segb`
- Virtuoso not reachable: check `docker compose -f docker-compose.yaml logs -f segb-virtuoso`
- Port conflicts: run `lsof -i :5000 -i :8080 -i :8890 -i :1111`
- Auth errors: read [Authentication and JWT](authentication-and-jwt.md)

## Related Pages

- [Quickstart](../getting-started/quickstart.md)
- [Authentication and JWT](authentication-and-jwt.md)
