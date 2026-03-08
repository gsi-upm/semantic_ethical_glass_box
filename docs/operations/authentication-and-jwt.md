# Authentication And JWT

## What This Page Explains

SEGB can run with or without authentication. This page explains:

- how auth mode is selected,
- which roles exist,
- how to generate a token,
- how to use that token in the API, scripts, and UI.

## How Auth Mode Works

SEGB looks at one setting:

- `SECRET_KEY`

### If `SECRET_KEY` Is Empty Or Unset

Authentication is disabled.

This is convenient for local learning and quick demos. Internally, the backend behaves as if the current user had all
roles available.

### If `SECRET_KEY` Is Set

Authentication is enabled.

In that mode:

- the backend expects an HS256 JWT,
- required claims are validated,
- route-level roles are enforced.

You can check the current mode with:

```bash
curl -s http://localhost:5000/auth/mode
```

## Roles

SEGB uses three practical roles:

| Role | Typical use |
|---|---|
| `logger` | robot or service that publishes logs |
| `auditor` | read-only access to reports, graph export, and queries |
| `admin` | operational and maintenance actions |

If you want the exact route matrix, see [API and Roles](../reference/api-and-roles.md).

## Generate A Token

Install the dependencies used by the token tool:

```bash
python3 -m pip install pyjwt fastapi
```

Then run the generator from the backend source directory:

```bash
(
  cd apps/backend/src
  SECRET_KEY="<same_secret_as_.env>" python3 -m tools.generate_jwt \
    --username demo_admin \
    --role admin \
    --expires-in 3600 \
    --json
)
```

Important details:

- the `SECRET_KEY` here must be exactly the same as the one in `.env`,
- the token tool expects a sufficiently long secret,
- `--json` is useful because it prints the token in machine-readable output.

## Useful Token Patterns

### Logger Token

Use this for robot-side publishing:

```bash
(
  cd apps/backend/src
  SECRET_KEY="<same_secret_as_.env>" python3 -m tools.generate_jwt \
    --username robot_logger \
    --role logger \
    --expires-in 3600 \
    --json
)
```

### Auditor Token

Use this for reports, graph exploration, and query work:

```bash
(
  cd apps/backend/src
  SECRET_KEY="<same_secret_as_.env>" python3 -m tools.generate_jwt \
    --username demo_auditor \
    --role auditor \
    --expires-in 3600 \
    --json
)
```

### Admin Token

Use this for shared-context review, graph deletion, Turtle validation, and system logs:

```bash
(
  cd apps/backend/src
  SECRET_KEY="<same_secret_as_.env>" python3 -m tools.generate_jwt \
    --username demo_admin \
    --role admin \
    --expires-in 3600 \
    --json
)
```

## Use A Token In The API

Pass it as a bearer token:

```bash
curl -s http://localhost:5000/events \
  -H "Authorization: Bearer <your_jwt>"
```

## Use A Token In Scripts

Some simulation and integration scripts accept `--token` directly:

```bash
./.segb_env/bin/python -m examples.simulations.run_use_case_02_report_ready_dataset \
  --publish-url http://localhost:5000 \
  --token "<admin_jwt>" \
  --no-print-ttl
```

For your own Python code, it is often cleaner to use an environment variable:

```bash
export SEGB_API_TOKEN="<logger_or_admin_jwt>"
```

Then read it in code and pass it to `SEGBPublisher`.

## Use A Token In The UI

Open:

- `http://localhost:8080/session`

Or, in development mode:

- `http://localhost:5173/session`

Paste the token there. The UI stores it in the browser session and then uses it for protected pages.

## Common Mistakes

- wrong secret: the token was signed with a different `SECRET_KEY`
- expired token: the page opens, but API requests fail
- wrong role: for example, using a `logger` token on `/reports`
- missing claims: SEGB expects at least `username`, `roles`, and `exp`

## Related Pages

- [Centralized Deployment](centralized-deployment.md)
- [Explore the Web UI](../guides/explore-the-web-ui.md)
- [API and Roles](../reference/api-and-roles.md)
