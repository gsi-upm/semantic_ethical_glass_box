# Authentication And JWT

SEGB has two practical modes. For a first contact, keep authentication off. Protected mode matters when you want
realistic access control between log publishers, readers, and operators.

## Learning Mode

If `SECRET_KEY` is empty or unset, authentication is disabled. This is the best choice for local demos and early
onboarding because the backend behaves as if all roles were available locally. You can check the current mode with:

```bash
curl -s http://localhost:5000/auth/mode
```

If you are only learning SEGB, you can stop here and continue with the rest of the guides without JWT setup.

## Protected Mode

If `SECRET_KEY` is set, the backend expects an HS256 JWT and enforces route-level roles. Use this mode when you need
real separation between log publishers, readers, and operators.

### Generate A Secret Key

Generate a cryptographically strong secret with Python's standard library:

```python
import secrets
print(secrets.token_urlsafe(32))
```

Copy the output into your `.env` file:

```bash
SECRET_KEY="<output_from_above>"
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

The `SECRET_KEY` here must be exactly the same as the one in `.env`. The token tool also expects a sufficiently long
secret, and `--json` is useful because it prints the token in machine-readable output.

## Useful Token Patterns

Use this pattern for robot-side publishing:

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

Use this pattern for reports, graph exploration, and query work:

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

Use this pattern for shared-context review, graph deletion, Turtle validation, and system logs:

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

Open `http://localhost:8080/session`, or `http://localhost:5173/session` in development mode. Paste the token there.
The UI stores it in the browser session and then uses it for protected pages.

## Common Mistakes

The most common failures are:

- Using the wrong secret
- Letting the token expire
- Using the wrong role for a route

## Related Pages

For deployment details, continue with [Centralized Deployment](centralized-deployment.md). For browser usage, see
[Explore the Web UI](../guides/explore-the-web-ui.md). For the exact route matrix, use
[API and Roles](../reference/api-and-roles.md).
