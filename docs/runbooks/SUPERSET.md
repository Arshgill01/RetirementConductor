# Disposable Superset native executor

This runbook exercises one bounded virtual-dataset migration against Apache
Superset 6.0.0 and disposable DataHub Core. Superset is now registered with the
campaign engine and CLI and the definitive producer gate performs an
independent read-only native refresh. It remains experimental because the
accepted boundary is disposable live-local evidence, not production RBAC,
dialect, or independent-operation evidence.

## Boundary

The executor supports exactly one virtual dataset whose SQL contains exactly
one unquoted legacy identifier. The dataset ID must be explicitly allowlisted.
Identity is the tuple of dataset ID/UUID, database ID/UUID, chart ID/UUID, and
the DataHub connector URL's `datasource_id`. Display names are never sufficient
for apply.

Apply is disabled by default and loopback endpoints are mandatory. Credentials
come only from environment variables and are never written into evidence.
Superset authentication uses database login to obtain a JWT bearer token and a
CSRF token.

## Start the pinned disposable service

Set fresh local-only values without committing them:

```bash
export SUPERSET_POSTGRES_PASSWORD='<local disposable value>'
export SUPERSET_ADMIN_PASSWORD='<local disposable value>'
export SUPERSET_SECRET_KEY='<local disposable value of at least 42 characters>'
export SUPERSET_METADATA_DATABASE_URI="postgresql+psycopg2://superset:${SUPERSET_POSTGRES_PASSWORD}@db:5432/superset"
docker compose -f deploy/superset/docker-compose.yml up -d --wait
```

The compose file binds Superset only to `127.0.0.1:18088` and pins both image
repository digests. The initialization SQL creates six public-safe synthetic
orders where `legacy_status` and `order_status` are equal.

Configure the native client and seed only through authenticated Superset APIs:

```bash
export SUPERSET_URL=http://127.0.0.1:18088
export SUPERSET_USERNAME=admin
export SUPERSET_PASSWORD="$SUPERSET_ADMIN_PASSWORD"
export SUPERSET_PROVIDER=db
export SUPERSET_PRINCIPAL=local-disposable-operator
export SUPERSET_VERSION=6.0.0
export SUPERSET_ALLOW_APPLY=false
export SUPERSET_ALLOWED_DATASET_IDS=1
export SUPERSET_SOURCE_DATABASE_URI="postgresql+psycopg2://superset:${SUPERSET_POSTGRES_PASSWORD}@db:5432/superset"
uv run python scripts/superset_seed.py
```

The seed refuses duplicate names and refuses an existing dataset that is not at
the exact before SQL. It does not reset drift. Use an approved compensation or
inspect and clean the disposable stack explicitly.

## Ingest and inspect DataHub

Start the repository's disposable DataHub Core, then run the official pinned
connector:

```bash
make datahub-core-up
export DATAHUB_GMS_URL=http://127.0.0.1:18080
uv run --python 3.11 --with 'acryl-datahub[superset]==1.6.0' \
  datahub ingest -c deploy/superset/datahub-recipe.yml
```

Inspect the dataset, chart, dashboard, ownership, and upstream-lineage aspects
directly in GMS. The supported connector contract is table-level lineage. In
the pinned live proof the SQL parser also emitted a fine-grained edge. That
edge is corroboration for this one SQL statement, not a general connector
guarantee. Direct native dataset SQL remains authoritative for exact field
dependence.

For the final gate, use a distinct principal with only Gamma plus the exact
database-access permission. The gate must reread the database, dataset, and
chart identities and SQL, force saved-chart execution, and prove that the
principal cannot update the dataset. The complete integrated setup and drift
matrix are in
[`DEFINITIVE_CONSEQUENTIAL.md`](DEFINITIVE_CONSEQUENTIAL.md).

## Plan, approval, apply, and validate

Use `retirement-conductor adapter superset plan` with a JSON array containing
the direct DataHub dataset entity and the seeded dataset/chart IDs. The
`authorize`, `apply`, `validate`, `reconcile`, and `compensate` subcommands use
the same campaign store and artifact directory as Git/dbt. Inspect the emitted
preflight and plan JSON. A separate operator approval is bound to:

- campaign ID;
- exact plan digest and source version;
- the sole `superset:dataset:<id>:<uuid>` target;
- `apply` capability (and `compensate` if recovery is authorized);
- the current authorization digest and expiry.

`SupersetWorkflow.apply` refuses before that record exists. On approval it
rereads immutable identities and the stable before fingerprint immediately
before one `PUT /api/v1/dataset/{id}`. A timeout is never retried: the executor
rereads the object and accepts only the exact after fingerprint; otherwise it
returns `APPLY_OUTCOME_UNKNOWN`.

`validate_and_emit_receipt` rereads the dataset and chart identities, forces
`GET /api/v1/chart/{id}/data/?force=true`, checks completeness, row count,
columns, and a public-safe sorted result digest, then compares the baseline and
post-change semantics. HTTP status and screenshots are not validators.

After connector reingestion, pass the direct reread to `reconcile`. Table-only
evidence refuses. The workstream proof requires the exact replacement edge,
absence of the legacy edge, unchanged native fingerprint, and another forced
native execution.

## Recovery

Compensation requires a separate approval with `compensate` scope and the exact
post-apply fingerprint. It restores the recorded before SQL and repeats forced
native validation. Any intervening owner change returns
`COMPENSATION_CONFLICT` without issuing a restore update.

Generate the inspected public summary only after successful apply, validation,
fresh connector reread, direct reconciliation, successful compensation, and
the two live refusal probes:

```bash
uv run python scripts/generate_superset_evidence.py \
  --plan .retirement-conductor/ws04-product-live/plan.json \
  --artifact-root .retirement-conductor/ws04-product-artifacts/ws04-live-product/superset \
  --refusal-evidence .retirement-conductor/ws04-product-live/refusals.json
```

Finally run:

```bash
uv run pytest -q tests/unit/test_superset.py tests/unit/test_superset_config.py
make check
```

The full live heterogeneous acceptance is:

```bash
make git-dbt-tool
make heterogeneous-campaign-acceptance
```

It requires the disposable services and the documented Superset environment.
Its public evidence is under `artifacts/public/heterogeneous-campaign/`.

## Teardown

The stack contains disposable synthetic data only:

```bash
docker compose -f deploy/superset/docker-compose.yml down -v
```

Removing `-v` preserves the local metadata volume for inspection. Never point
this initial executor at a non-loopback or production Superset.
