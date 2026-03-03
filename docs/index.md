# SEGB Documentation

This documentation is written for engineers who need to deploy, understand, and use SEGB quickly.

## Core Guides

- [Centralized deployment](deployment_centralized.md)
- [Install `semantic_log_generator`](semantic_log_generator_installation.md)
- [Use `semantic_log_generator`](semantic_log_generator_usage.md)
- [Real-world integration example](semantic_log_generator_real_world_integration.md)
- [Use the web UI to inspect data](web_observability.md)
- [How TTL is generated internally](ttl_generation_internals.md)

## Additional Technical Docs

- [Shared-context resolver details](backend/shared_context.md)
- [Monorepo structure](monorepo_structure.md)

## Fast Entry Point

If you only need to run the full flow quickly:

1. (Optional) Copy `.env.example` to `.env` to override defaults.
2. Deploy with Docker Compose.
3. Create a Python virtualenv and install `semantic_log_generator`.
4. Run the report-ready simulation use case to publish sample data.
5. Open the web UI and review Reports + KG Graph views.

See details in [Centralized deployment](deployment_centralized.md).

To serve this documentation locally:

```bash
python -m pip install -r docs/requirements.txt
mkdocs serve
```
