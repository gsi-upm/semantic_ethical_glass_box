#!/bin/sh
# Provisions the read-only Virtuoso account used by GET /query.
#
# Runs inside the Virtuoso image (it needs `isql`) and logs in as the admin account. Safe to run on every start:
#   - creates the reader user, or resets its password if it already exists;
#   - leaves it with exactly one role, SPARQL_SELECT (any other role, and what it inherits, is revoked);
#   - sets its default permissions on every graph, public and private, to none;
#   - grants it read (and nothing else) on the events graph.
# Existing accounts with direct SQL grants are refused before any account changes. The reader's effective SQL
# privileges (its own, those of its roles, and those of PUBLIC and nobody) must then equal the reviewed manifest
# reader-sql-policy.manifest, which also records an MD5 of the body of every granted routine that has one. Anything
# else (a new grant, a different role, a replaced routine body) makes provisioning fail. On success the digest of the
# verified listing is stored in DB.DBA.SEGB_QUERY_READER_POLICY; the backend compares it with the live listing at
# startup. See docs/operations/centralized-deployment.md.
# It then checks the effective permissions Virtuoso computes, which include what every user inherits from `nobody`,
# and exits non-zero unless the reader can read the events graph, cannot write it, and cannot touch the audit graph.
#
# Environment:
#   VIRTUOSO_ADMIN_PASSWORD   required, the admin (DBA) password
#   VIRTUOSO_READER_PASSWORD  required
#   VIRTUOSO_READER_USER      default segb_reader
#   VIRTUOSO_ADMIN_USER       default dba
#   VIRTUOSO_ISQL_ADDRESS     default segb-virtuoso:1111
#   VIRTUOSO_GRAPH_URI        default http://segb/events
#   VIRTUOSO_AUDIT_GRAPH_URI  default http://segb/audit
#   VIRTUOSO_PROVISION_WAIT_SECONDS  how long to wait for Virtuoso to accept logins, default 180
#   VIRTUOSO_READER_POLICY_FILE  reviewed SQL privilege manifest, default reader-sql-policy.manifest next to this script
#   VIRTUOSO_PRINT_READER_POLICY=1  print the reader's effective SQL privilege listing instead of comparing it, to
#                                   regenerate the manifest on a disposable database

set -eu

fail() {
    echo "provision-query-reader: $*" >&2
    exit 1
}

: "${VIRTUOSO_ADMIN_PASSWORD:?VIRTUOSO_ADMIN_PASSWORD is required}"
: "${VIRTUOSO_READER_PASSWORD:?VIRTUOSO_READER_PASSWORD is required}"
reader="${VIRTUOSO_READER_USER-segb_reader}"
admin="${VIRTUOSO_ADMIN_USER:-dba}"
address="${VIRTUOSO_ISQL_ADDRESS:-segb-virtuoso:1111}"
events_graph="${VIRTUOSO_GRAPH_URI:-http://segb/events}"
audit_graph="${VIRTUOSO_AUDIT_GRAPH_URI:-http://segb/audit}"
wait_seconds="${VIRTUOSO_PROVISION_WAIT_SECONDS:-180}"
policy_file="${VIRTUOSO_READER_POLICY_FILE:-$(dirname "$0")/reader-sql-policy.manifest}"
print_policy="${VIRTUOSO_PRINT_READER_POLICY:-0}"

# Command substitution would silently drop a trailing newline from the quoted password, and isql reads statements
# line by line, so refuse such passwords instead of provisioning a different one than the backend will send.
newline='
'
carriage_return=$(printf '\r')
for secret in "$VIRTUOSO_ADMIN_PASSWORD" "$VIRTUOSO_READER_PASSWORD"; do
    case "$secret" in
        *"$newline"* | *"$carriage_return"*) fail "Passwords must not contain line breaks." ;;
    esac
done

case "$reader" in
    "" | [!A-Za-z_]* | *[!A-Za-z0-9_]*) fail "VIRTUOSO_READER_USER must match [A-Za-z_][A-Za-z0-9_]*." ;;
esac
reader_lower=$(printf '%s' "$reader" | tr '[:upper:]' '[:lower:]')
admin_lower=$(printf '%s' "$admin" | tr '[:upper:]' '[:lower:]')
case "$reader_lower" in
    dba | nobody | sparql | "$admin_lower") fail "VIRTUOSO_READER_USER must be a dedicated account, not '$reader'." ;;
esac
for graph in "$events_graph" "$audit_graph"; do
    case "$graph" in
        "" | *[!A-Za-z0-9:/._~%#?=\&+@-]*) fail "Graph IRIs may only contain IRI characters: '$graph'." ;;
    esac
done
[ "$events_graph" != "$audit_graph" ] || fail "The events and audit graphs must differ."

# SQL string literal: Virtuoso reads backslash escapes inside quotes, so double backslashes and quotes. isql also
# expands $-macros inside strings (it rewrites "a$HHMMSS" and "cost$5"), so each dollar sign is spliced in as chr(36).
sql_string() {
    printf "'%s'" "$(printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e "s/'/''/g" -e "s/[\$]/' || chr(36) || '/g")"
}

isql_admin() {
    isql "$address" "$admin" "$VIRTUOSO_ADMIN_PASSWORD" "$@"
}

deadline=$(($(date +%s) + wait_seconds))
until isql_admin "exec=select 1" >/dev/null 2>&1; do
    [ "$(date +%s)" -lt "$deadline" ] || fail "Could not log in to Virtuoso at $address as $admin."
    sleep 2
done

output=$(isql_admin <<SQL 2>&1
-- Effective SQL privileges of the reader, one text line each: grants held by the reader itself, by every role it
-- inherits, by PUBLIC (user id 1) and by nobody, plus the role names. A routine's body hash comes from
-- SYS_PROCEDURES; objects without a stored body (Virtuoso's built-ins) show '-', so replacing one adds a hash.
-- Source: https://docs.openlinksw.com/virtuoso/usersystables/
create function DB.DBA.SEGB_QUERY_READER_SQL_POLICY_LINES (in reader varchar) returns any
{
  declare reader_id integer;
  declare lines any;
  reader_id := (select U_ID from DB.DBA.SYS_USERS where U_NAME = reader and U_IS_ROLE = 0);
  if (reader_id is null)
    signal ('SEGB5', 'the query reader must be an existing dedicated user');
  lines := vector ();
  for (select case when G.G_USER = reader_id then 'READER' when G.G_USER = 1 then 'PUBLIC' else U.U_NAME end as grantee,
              G.G_OP as op, G.G_OBJECT as obj, coalesce (G.G_COL, '') as col,
              coalesce ((select md5 (coalesce (P.P_TEXT, '')) from DB.DBA.SYS_PROCEDURES P where P.P_NAME = G.G_OBJECT), '-') as body
         from DB.DBA.SYS_GRANTS G left outer join DB.DBA.SYS_USERS U on U.U_ID = G.G_USER
        where G.G_USER in (reader_id, 1)
           or G.G_USER in (select U_ID from DB.DBA.SYS_USERS where U_NAME = 'nobody')
           or G.G_USER in (select GI_SUB from DB.DBA.SYS_ROLE_GRANTS where GI_SUPER = reader_id)) do
    lines := vector_concat (lines, vector (sprintf ('%s|%d|%s|%s|%s', grantee, op, obj, col, body)));
  for (select U.U_NAME as role_name from DB.DBA.SYS_ROLE_GRANTS R, DB.DBA.SYS_USERS U
        where R.GI_SUPER = reader_id and R.GI_SUB = U.U_ID) do
    lines := vector_concat (lines, vector (sprintf ('ROLE|%s', role_name)));
  -- Objects created under the reader's own schema carry implicit owner rights without any SYS_GRANTS row.
  for (select distinct KEY_TABLE as owned from DB.DBA.SYS_KEYS where name_part (KEY_TABLE, 1) = reader) do
    lines := vector_concat (lines, vector (sprintf ('OWNS|%s', owned)));
  for (select P_NAME as owned from DB.DBA.SYS_PROCEDURES where name_part (P_NAME, 1) = reader) do
    lines := vector_concat (lines, vector (sprintf ('OWNS|%s', owned)));
  return __vector_sort (lines);
}
;
create function DB.DBA.SEGB_QUERY_READER_SQL_POLICY_DIGEST_OF (in lines any) returns varchar
{
  declare acc varchar;
  declare i integer;
  acc := '';
  for (i := 0; i < length (lines); i := i + 1)
    acc := concat (acc, lines[i], '\n');
  return md5 (acc);
}
;
create procedure DB.DBA.SEGB_QUERY_READER_SQL_POLICY_ROWS (in reader varchar)
{
  declare lines any;
  declare i integer;
  declare l varchar;
  lines := DB.DBA.SEGB_QUERY_READER_SQL_POLICY_LINES (reader);
  result_names (l);
  for (i := 0; i < length (lines); i := i + 1)
    result (lines[i]);
  -- Digest of exactly the lines printed above, so the stored digest is the one that was compared.
  result (concat ('DIGEST|', DB.DBA.SEGB_QUERY_READER_SQL_POLICY_DIGEST_OF (lines)));
}
;
create function DB.DBA.SEGB_QUERY_READER_SQL_POLICY_DIGEST (in reader varchar) returns varchar
{
  return DB.DBA.SEGB_QUERY_READER_SQL_POLICY_DIGEST_OF (DB.DBA.SEGB_QUERY_READER_SQL_POLICY_LINES (reader));
}
;
create procedure DB.DBA.SEGB_QUERY_READER_POLICY_TABLE ()
{
  if (not exists (select 1 from DB.DBA.SYS_KEYS where KEY_TABLE = 'DB.DBA.SEGB_QUERY_READER_POLICY'))
    exec ('create table DB.DBA.SEGB_QUERY_READER_POLICY (R_USER varchar primary key, R_DIGEST varchar not null)');
}
;
DB.DBA.SEGB_QUERY_READER_POLICY_TABLE ();
-- 0 only when the digest stored by provisioning equals the live listing. A missing row counts as drift.
-- No EXECUTE grant is given to the reader or PUBLIC: the backend calls it with the administrative account.
create function DB.DBA.SEGB_QUERY_READER_SQL_POLICY_DRIFT (in reader varchar) returns integer
{
  declare stored varchar;
  stored := (select R_DIGEST from DB.DBA.SEGB_QUERY_READER_POLICY where R_USER = reader);
  if (stored is null or stored <> DB.DBA.SEGB_QUERY_READER_SQL_POLICY_DIGEST (reader))
    return 1;
  return 0;
}
;
create procedure DB.DBA.SEGB_QUERY_READER_SQL_POLICY_STORE (in reader varchar, in verified_digest varchar)
{
  delete from DB.DBA.SEGB_QUERY_READER_POLICY where R_USER = reader;
  insert into DB.DBA.SEGB_QUERY_READER_POLICY (R_USER, R_DIGEST) values (reader, verified_digest);
}
;
create procedure DB.DBA.SEGB_PROVISION_QUERY_READER (
  in reader varchar, in pwd varchar, in events_graph varchar, in audit_graph varchar)
{
  declare reader_id, perms, i integer;
  declare extra_roles any;
  if (exists (select 1 from DB.DBA.SYS_USERS where U_NAME = reader and U_IS_ROLE = 1))
    signal ('SEGB1', sprintf ('%s is a role, the query reader must be a dedicated user', reader));
  -- Whatever happens next, the backend must not accept this account until the policy check below has passed.
  delete from DB.DBA.SEGB_QUERY_READER_POLICY where R_USER = reader;
  if (exists (select 1 from DB.DBA.SYS_USERS where U_NAME = reader))
    if (exists (select 1 from DB.DBA.SYS_GRANTS G, DB.DBA.SYS_USERS U where U.U_NAME = reader and G.G_USER = U.U_ID))
      signal ('SEGB5', 'the query reader has direct SQL grants; revoke them before provisioning');
  if (exists (select 1 from DB.DBA.SYS_USERS where U_NAME = reader))
    DB.DBA.USER_PASSWORD_SET (reader, pwd);
  else
    DB.DBA.USER_CREATE (reader, pwd);
  reader_id := (select U_ID from DB.DBA.SYS_USERS where U_NAME = reader);

  extra_roles := (select vector_agg (R.U_NAME) from DB.DBA.SYS_ROLE_GRANTS, DB.DBA.SYS_USERS R
                  where GI_SUPER = reader_id and GI_SUB = R.U_ID and GI_DIRECT = 1 and R.U_NAME <> 'SPARQL_SELECT');
  for (i := 0; i < length (extra_roles); i := i + 1)
    DB.DBA.USER_REVOKE_ROLE (reader, extra_roles[i]);
  if (not exists (select 1 from DB.DBA.SYS_ROLE_GRANTS, DB.DBA.SYS_USERS R
                  where GI_SUPER = reader_id and GI_SUB = R.U_ID and R.U_NAME = 'SPARQL_SELECT'))
    DB.DBA.USER_GRANT_ROLE (reader, 'SPARQL_SELECT');

  -- Clear old graph grants too, including the previous events graph after a configuration change.
  -- Source: https://docs.openlinksw.com/virtuoso/fn_rdf_all_user_perms_del/
  DB.DBA.RDF_ALL_USER_PERMS_DEL (reader);
  DB.DBA.RDF_DEFAULT_USER_PERMS_SET (reader, 0, 0);
  DB.DBA.RDF_DEFAULT_USER_PERMS_SET (reader, 0, 1);
  DB.DBA.RDF_GRAPH_USER_PERMS_DEL (audit_graph, reader);
  DB.DBA.RDF_GRAPH_USER_PERMS_SET (events_graph, reader, 1);

  -- SPARQL_SELECT itself includes SPARQL_LOAD_SERVICE_DATA; anything else (SPARQL_UPDATE, SPARQL_SPONGE, ...) means
  -- someone nested a broader role into SPARQL_SELECT.
  if (exists (select 1 from DB.DBA.SYS_ROLE_GRANTS, DB.DBA.SYS_USERS R
              where GI_SUPER = reader_id and GI_SUB = R.U_ID
              and R.U_NAME not in ('SPARQL_SELECT', 'SPARQL_LOAD_SERVICE_DATA')))
    signal ('SEGB2', 'the query reader inherits roles beyond SPARQL_SELECT, check what SPARQL_SELECT is granted');
  perms := DB.DBA.RDF_GRAPH_USER_PERMS_GET (audit_graph, reader);
  if (perms <> 0)
    signal ('SEGB3', sprintf ('the query reader has permissions %d on the audit graph, check what nobody is granted there', perms));
  perms := DB.DBA.RDF_GRAPH_USER_PERMS_GET (events_graph, reader);
  if (perms <> 1)
    signal ('SEGB4', sprintf ('the query reader has permissions %d on the events graph instead of read only, check what nobody is granted there', perms));
}
;
DB.DBA.SEGB_PROVISION_QUERY_READER ($(sql_string "$reader"), $(sql_string "$VIRTUOSO_READER_PASSWORD"), $(sql_string "$events_graph"), $(sql_string "$audit_graph"));
drop procedure DB.DBA.SEGB_PROVISION_QUERY_READER;
select 'SEGB_QUERY_READER_PROVISIONED';
SQL
) || fail "isql failed."

# isql exits 0 even when a statement fails. Report only the error lines: the statement echo would show the password.
errors=$(printf '%s\n' "$output" | grep '\*\*\* Error' || true)
[ -z "$errors" ] || fail "$errors"
printf '%s\n' "$output" | grep -q '^SEGB_QUERY_READER_PROVISIONED' || fail "isql did not confirm provisioning."

# Effective SQL privileges (including everything inherited from roles, PUBLIC and nobody) must equal the reviewed
# manifest. isql prints the listing as rows; keep only the policy lines.
policy_output=$(isql_admin "exec=DB.DBA.SEGB_QUERY_READER_SQL_POLICY_ROWS($(sql_string "$reader"))" 2>&1) || fail "isql failed."
errors=$(printf '%s\n' "$policy_output" | grep '\*\*\* Error' || true)
[ -z "$errors" ] || fail "$errors"
actual=$(printf '%s\n' "$policy_output" | grep '^[A-Za-z_]*|' | grep -v '^DIGEST|' | LC_ALL=C sort)
verified_digest=$(printf '%s\n' "$policy_output" | sed -n 's/^DIGEST|\([0-9a-f]\{32\}\).*/\1/p' | head -n 1)
if [ "$print_policy" = "1" ]; then
    printf '%s\n' "$actual"
    exit 0
fi
[ -r "$policy_file" ] || fail "Cannot read the reviewed SQL privilege manifest '$policy_file'."
expected=$(grep '^[A-Za-z_]*|' "$policy_file" | LC_ALL=C sort)
if [ "$actual" != "$expected" ]; then
    scratch=$(mktemp -d)
    printf '%s\n' "$expected" > "$scratch/expected"
    printf '%s\n' "$actual" > "$scratch/actual"
    differences=$(diff "$scratch/expected" "$scratch/actual" || true)
    rm -rf "$scratch"
    fail "the query reader has direct SQL grants or its effective SQL privileges differ from the reviewed manifest (< manifest, > database):
$differences"
fi
[ -n "$verified_digest" ] || fail "isql did not report the digest of the verified SQL privileges."
store_output=$(isql_admin "exec=DB.DBA.SEGB_QUERY_READER_SQL_POLICY_STORE($(sql_string "$reader"), $(sql_string "$verified_digest"))" 2>&1) || fail "isql failed."
errors=$(printf '%s\n' "$store_output" | grep '\*\*\* Error' || true)
[ -z "$errors" ] || fail "$errors"
echo "provision-query-reader: '$reader' is read-only: it reads <$events_graph> and has no triple access to <$audit_graph>."
