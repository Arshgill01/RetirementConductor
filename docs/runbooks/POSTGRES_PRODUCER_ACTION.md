# PostgreSQL producer action runbook

This runbook exercises CP-01's exact producer action against a disposable,
loopback-only PostgreSQL service. It is not connected to the shared producer
gate on this branch.

## Safety boundary

The action supports exactly one operation:

```sql
ALTER TABLE "retirement_lab"."orders" DROP COLUMN "legacy_status";
```

The module constructs quoted identifiers from a digest-bound target. It does
not accept SQL, `CASCADE`, predicates, or multiple operations. Apply defaults
off. Planning uses `rc_cp01_observer`; execution requires the separately
instantiated `rc_cp01_mutator`, which owns only the disposable fixture table.
The service binds PostgreSQL to `127.0.0.1:25432` under Compose project
`rc_cp01_producer`.

Dropping a populated column is not reversible. Recovery in this experiment is
full deterministic reconstruction of the disposable Docker volume. Do not use
this runbook against production, shared, or non-loopback PostgreSQL.

## Run focused checks

```bash
uv run pytest -q \
  tests/unit/test_postgres_producer.py \
  tests/unit/test_postgres_producer_config.py

RC_CP01_RUN_LIVE=1 \
uv run pytest -q tests/integration/test_postgres_producer_action.py
```

The live test creates random ignored runtime credentials, reconstructs each
fixture variant, runs the frozen matrix, writes public-safe aggregate evidence,
and removes the containers, network, and volume in a `finally` block. It uses
only the reserved CP-01 service and port.

The equivalent direct evidence command is:

```bash
uv run python scripts/run_postgres_producer_acceptance.py
```

The command refuses if port `25432` is already occupied. Raw task evidence is
kept under `.retirement-conductor/cp01/`; it is ignored by Git. Public evidence
is written to `artifacts/public/postgres-producer-action/index.json` and never
contains credentials, DSNs, row values, private paths, or raw server logs.

## What to inspect

Confirm the public index records:

- the frozen fixture digest before observation;
- PostgreSQL, Docker, and Compose versions;
- safe endpoint, principal, capability, and allowlist facts;
- before and after schema fingerprints;
- one clean commit, lost-response recovery, replay refusal, and one-winner
  concurrent execution;
- every frozen refusal code and native column-presence result;
- exact destructive statement counts;
- a canonical `index_digest`;
- the limitation that only a disposable PostgreSQL column was removed.

Also confirm there is no remaining CP-01 container or volume:

```bash
docker ps -a --filter name=rc_cp01_producer
docker volume ls --filter name=rc_cp01_producer
```

## Failure recovery

If service startup fails, inspect the ignored
`.retirement-conductor/cp01/private/compose-up-failure.log`. Do not publish it.
Run the Compose teardown with the same project name before retrying:

```bash
COMPOSE_PROJECT_NAME=rc_cp01_producer \
docker compose -f deploy/postgres-producer/docker-compose.yml \
  down --volumes --remove-orphans
```

An `OUTCOME_UNKNOWN` attempt must not be applied again. Invoke the module's
explicit native `resolve_outcome` path after observer connectivity returns. A
native reread may classify it as `COMMITTED` or `NOT_COMMITTED`; any different
schema remains `OUTCOME_UNKNOWN` for operator investigation.
