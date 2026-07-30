# Disposable DataHub Core runbook

This runbook creates a project-isolated DataHub Core v1.6.0 graph for the
phase 02 live evidence boundary. It does not use retained quickstart volumes,
host credentials, production endpoints, or DataHub UI authentication.

## Start isolated Core

Generate ignored local token-service material and start only GMS plus its
private storage dependencies:

```bash
uv run python scripts/datahub_core_env.py
docker compose \
  --env-file .retirement-conductor/datahub/core.env \
  -f deploy/datahub/docker-compose.core.yml \
  up -d --wait datahub-gms
```

Only GMS is published, on loopback port `18080`. MySQL, Kafka, and OpenSearch
remain on the private Compose network. The Compose project and all three named
volumes are distinct from any other DataHub quickstart. The disposable
OpenSearch node disables disk allocation watermarks because shared development
hosts can be above the default threshold; repository and host disk capacity
must still be checked before startup.

## Seed the public-safe graph

Run the pinned DataHub SDK in an isolated Python 3.11 environment:

```bash
DATAHUB_GMS_URL=http://127.0.0.1:18080 \
uv run --python 3.11 --with 'acryl-datahub==1.6.0' \
  python scripts/datahub_seed.py
```

The seeder is idempotent. It creates one stable Snowflake target with
`legacy_status` and `order_status`, three dbt intermediates, eighteen
cross-platform dataset consumers, six charts, and four dashboards. The
fixture is synthetic and contains no private query text or credentials.

## Start the pinned MCP server

Use MCP server version 0.6.0 at source commit
`9a6946daa7d30eb481c82dd8ee5e15ae6526a3c9`:

```bash
DATAHUB_GMS_URL=http://127.0.0.1:18080 \
DATAHUB_SKIP_CONFIG=true \
DATAHUB_MCP_DISABLE_DEFAULT_VIEW=true \
TOOLS_IS_MUTATION_ENABLED=true \
SAVE_DOCUMENT_TOOL_ENABLED=true \
uv --directory /path/to/mcp-server-datahub \
  run --frozen mcp-server-datahub --transport http
```

Do not set a token for this loopback-only, authentication-disabled disposable
Core instance. A real endpoint must supply a secret reference through the
environment instead.

## Stop without crossing project scope

```bash
docker compose \
  --env-file .retirement-conductor/datahub/core.env \
  -f deploy/datahub/docker-compose.core.yml \
  down
```

This retains only the isolated disposable volumes for inspection. Removing
those volumes is a separate destructive action and is not part of this
runbook.
