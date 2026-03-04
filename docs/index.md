# SEGB Documentation

SEGB documentation is organized in one linear path so you can run the stack first and learn features progressively.

## Recommended Path (Order to Follow)

1. [Centralized Deployment (Backend + Frontend)](deployment/centralized.md)
2. [Install `semantic_log_generator`](package/installation.md)
3. [Basic Use: Post Your First Log to SEGB](package/usage.md)
4. [Learn Main SEGB Features (Simple)](getting-started/segb-features.md)
5. [Real Use Case with Robot Simulator (ROS4HRI)](package/ros4hri-integration.md)

## Additional Guides

- [Quickstart](getting-started/quickstart.md)
- [Web Observability](operations/web-observability.md)

## Backend and Internals

- [Shared Context Resolution](backend/shared-context.md)
- [TTL Generation Pipeline](internals/ttl-generation.md)

## Reference

- [Monorepo Structure](reference/monorepo-structure.md)

## Local Docs Preview

```bash
python -m pip install -r docs/requirements.txt
mkdocs serve
```
