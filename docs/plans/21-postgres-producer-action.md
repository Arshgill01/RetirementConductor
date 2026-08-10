# CP-01 — bounded PostgreSQL producer retirement action

## Objective

Build and prove one concrete producer action that removes an exact legacy
column from a disposable PostgreSQL database. The action boundary must be safe
enough for CP-05 to place behind the existing one-use producer gate without
turning Retirement Conductor into an arbitrary SQL executor.

## Product question

Can the protocol control a real, separately privileged schema retirement while
preserving exact scope, precondition checking, one-use intent, native outcome
verification, and failure-closed recovery?

## Required action

The only supported mutation is structurally equivalent to:

```sql
ALTER TABLE "retirement_lab"."orders" DROP COLUMN "legacy_status";
```

The schema, table, and column come from a frozen allowlisted fixture. They must
be quoted as identifiers by deterministic code, never interpolated as raw SQL.
`CASCADE`, multiple statements, arbitrary predicates, and user-supplied SQL are
forbidden.

## Scope

Implement a concrete boundary, not a generic warehouse adapter framework:

- secret-safe loopback-only PostgreSQL settings;
- exact database, schema, table, column, replacement-column, server-version,
  table-identity, and before-schema fingerprint observation;
- read-only planning with a deterministic action digest;
- apply-off-by-default and exact tuple allowlisting;
- a separately instantiated mutation client/principal;
- transaction-scoped table lock and immediate pre-action fingerprint reread;
- `DROP COLUMN` without `CASCADE`;
- in-transaction and post-commit schema verification;
- action result containing safe identities and digests, never credentials or
  data rows;
- native resolution of timeout or lost-response outcomes by schema reread;
- explicit refusal of blind retry when the native outcome remains ambiguous;
- deterministic fixture reconstruction for the disposable environment.

Do not wire this module into `ProducerGateWorkflow`, CLI, MCP, schemas, or
canonical product documents in this branch. CP-05 owns that integration.

## Trusted-boundary design requirements

The implementation must distinguish:

1. **observer capability** — connect and read catalog/schema facts;
2. **mutation capability** — alter only the allowlisted object;
3. **campaign authority** — absent from this module; supplied later by the
   producer gate.

The public configuration summary may record credential-reference presence,
principal identity, endpoint identity digest, PostgreSQL version, and allowed
tuple. It must never record passwords or connection strings containing them.

The action plan must bind at least:

- database identity and PostgreSQL version;
- schema, table, legacy column, and replacement column;
- stable native table identity when available;
- complete ordered column-definition fingerprint;
- legacy and replacement type/nullability/default facts;
- dependency check result;
- allowlist/configuration digest;
- planned action type `postgres_drop_column_v1`;
- action digest and expiry supplied by the integration caller.

The executor must refuse if:

- the endpoint is non-loopback;
- apply is not explicitly enabled;
- the exact tuple is not allowlisted;
- the legacy field is missing during planning;
- the replacement field is missing or incompatible;
- the table identity or schema fingerprint changed;
- native dependencies would require `CASCADE`;
- the mutation principal lacks exact permission;
- more than one action is requested;
- the confirmed action digest differs;
- the outcome of an earlier attempt is unknown and native reread cannot
  establish presence or absence.

## Outcome semantics

Classify native outcomes explicitly:

- `NOT_STARTED` — precondition or permission refused before SQL execution;
- `COMMITTED` — post-commit reread proves the legacy column is absent;
- `NOT_COMMITTED` — rollback or native reread proves the legacy column remains;
- `OUTCOME_UNKNOWN` — neither state can be established safely.

An `OUTCOME_UNKNOWN` attempt is terminal until an explicit observation command
resolves it. Do not automatically rerun `ALTER TABLE`.

Because dropping a populated column destroys its values, do not claim general
reversibility. Recovery for this experiment is full deterministic recreation
of the disposable database. That limitation must appear in evidence.

## Acceptance matrix

### Clean native success

- Seed the exact table and prove both fields exist.
- Produce one plan while mutation is disabled.
- Enable the mutation boundary with its separate principal.
- Execute the exact confirmed plan once.
- Prove from `pg_catalog` after commit that `legacy_status` is absent and
  `order_status` remains unchanged.
- Prove a second execution cannot perform another action.

### Failure-closed cases

At minimum prove:

- missing allowlist;
- apply disabled;
- wrong schema/table/column;
- non-loopback endpoint;
- source fingerprint drift;
- replacement type drift;
- dependent object requiring `CASCADE`;
- insufficient mutation permission;
- wrong confirmed digest;
- connection loss before execution;
- injected connection loss after intent/before outcome observation;
- replay after committed success;
- concurrent duplicate attempt.

For every refusal before mutation, native reread must prove the column remains.
For the lost-response case, preserve the first attempt and resolve from native
state rather than retrying blindly.

## Evidence

Create task-local artifacts under:

```text
artifacts/public/postgres-producer-action/
```

The public index must contain:

- frozen fixture digest;
- safe configuration and version facts;
- before/after schema digests;
- action plan and outcome digests;
- exact refusal-code matrix;
- count of destructive statements attempted and committed;
- replay result;
- limitation that only a disposable PostgreSQL column was removed;
- canonical self-digest.

Do not publish row values, native credentials, DSNs, host paths, or raw server
logs. Keep raw logs under ignored runtime state.

## Owned files

Prefer new task-local paths such as:

- `src/retirement_conductor/postgres_producer.py`;
- `src/retirement_conductor/postgres_producer_config.py`;
- `deploy/postgres-producer/`;
- `scripts/run_postgres_producer_acceptance.py`;
- `tests/unit/test_postgres_producer*.py`;
- `tests/integration/test_postgres_producer_action.py`;
- `docs/runbooks/POSTGRES_PRODUCER_ACTION.md`;
- `docs/plans/integration-notes-postgres-producer.md`.

Follow the frozen-file rules in the coordination plan. If a new dependency is
truly required, do not edit `pyproject.toml`; record the exact dependency and
reason for CP-05. Prefer the standard library or the PostgreSQL CLI already in
the pinned disposable image.

## Validation

Run focused unit and live-local integration tests, inspect every generated
artifact, then run `make check`.

## Completion recommendation

Return one of:

- `KEEP` — exact live action, native verification, and failure matrix pass;
- `SIMPLIFY` — the action works but part of the design adds no safety value;
- `REMOVE` — a safely bounded action cannot be built without arbitrary SQL or
  broad authority;
- `INCONCLUSIVE` — live PostgreSQL evidence could not be completed.
