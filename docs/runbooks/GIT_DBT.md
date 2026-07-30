# Git/dbt disposable runbook

This runbook exercises the supported repository path against the public-safe
dbt project and ignored local campaign state. It never merges a branch or
connects to a production warehouse.

## Safety boundary

- `GIT_DBT_ALLOW_APPLY` defaults to `false`.
- The declared repository, branch, commit, file, token, and fingerprints must
  match before apply.
- Approval is a separate digest-bound campaign record.
- Git hooks, global configuration, external dbt packages, traversal, and
  symlinks are refused or bypassed.
- dbt runs from a copied project in bubblewrap with no host home or source
  repository mount, an unshared network, an allowlisted environment, and
  bounded resources.
- Runtime repositories, SQLite state, logs, and raw artifacts remain under
  `.retirement-conductor/` and are ignored.

## Prerequisites

Start and seed the disposable DataHub Core boundary as described in
[DATAHUB_CORE.md](DATAHUB_CORE.md), then install the pinned dbt-DuckDB tool and
prepare the deterministic repository:

```bash
make git-dbt-tool
make git-dbt-workspace
make datahub-seed
```

Set only non-secret local boundary configuration:

```bash
export DATAHUB_GMS_URL=http://127.0.0.1:18080
export DATAHUB_MCP_URL=http://127.0.0.1:8000/mcp
export DATAHUB_PRINCIPAL=anonymous-disposable-core
export GIT_DBT_REPOSITORY_ROOT=.retirement-conductor/workspaces/ret-orders-git-dbt/repository
export GIT_DBT_DBT_EXECUTABLE=.retirement-conductor/tools/dbt-duckdb-1.10.1/bin/dbt
export GIT_DBT_ALLOW_APPLY=true
```

The apply flag authorizes only the adapter capability. It does not replace the
campaign approval.

## Create, inventory, and plan

Use trusted RFC-3339 timestamps for durable events:

```bash
retirement-conductor campaign create \
  fixtures/specs/git-dbt-live.yaml \
  --store .retirement-conductor/campaigns.sqlite \
  --writer-id local-operator \
  --occurred-at 2026-07-30T10:00:00Z

retirement-conductor adapter git-dbt preflight \
  --campaign ret-orders-git-dbt

retirement-conductor adapter git-dbt plan \
  --campaign ret-orders-git-dbt
```

Inspect the preflight, inventory binding, and plan under
`.retirement-conductor/artifacts/ret-orders-git-dbt/git-dbt/`. Confirm the
DataHub URN, dbt unique ID, source commit, main-only search limitation, exact
file, before/after fingerprints, replacement types, and target branch before
authorizing. Copy the exact displayed plan digest into
`RC_PLAN_DIGEST` only after that review:

```bash
export RC_PLAN_DIGEST='<exact-plan-digest-from-reviewed-plan>'
```

## Authorize and apply

Authorization binds one principal to the exact plan, source commit, target set,
authorization configuration, and expiry:

```bash
retirement-conductor adapter git-dbt authorize \
  --campaign ret-orders-git-dbt \
  --authorized-at 2026-07-30T10:05:00Z \
  --expires-at 2026-07-30T11:05:00Z

retirement-conductor adapter git-dbt apply \
  --campaign ret-orders-git-dbt \
  --confirm-plan-digest "$RC_PLAN_DIGEST"
```

Inspect the disposable repository with ordinary Git commands. The review
branch must be clean and its diff from the pinned source commit must name only
`models/orders_model_00.sql`. Repeating the same apply must retain the same
commit and apply digest. Missing confirmation refuses with
`AUTH_APPROVAL_MISSING`; a digest other than the current approved plan refuses
with `AUTH_APPROVAL_WRONG_PLAN`.

## Exercise recovery

For the acceptance run, compensate the first apply, verify the restored branch,
then plan and separately approve a reapply:

```bash
retirement-conductor adapter git-dbt compensate \
  --campaign ret-orders-git-dbt

retirement-conductor adapter git-dbt plan \
  --campaign ret-orders-git-dbt

export RC_PLAN_DIGEST='<exact-reapply-plan-digest>'

retirement-conductor adapter git-dbt authorize \
  --campaign ret-orders-git-dbt \
  --authorized-at 2026-07-30T10:15:00Z \
  --expires-at 2026-07-30T11:15:00Z

retirement-conductor adapter git-dbt apply \
  --campaign ret-orders-git-dbt \
  --confirm-plan-digest "$RC_PLAN_DIGEST"
```

Compensation refuses if the applied file or branch changed after apply. It
does not overwrite an intervening owner edit.

## Validate and evaluate

```bash
retirement-conductor adapter git-dbt validate \
  --campaign ret-orders-git-dbt

retirement-conductor campaign evaluate \
  --campaign ret-orders-git-dbt

make phase03-evidence
make check
git diff --check
```

Validation must show successful `dbt parse`, `dbt seed`, `dbt build`, and
`dbt test` commands and one live receipt for the exact campaign consumer.
Before phase 04 reconciliation, the rich graph campaign is expected to remain
`UNSAFE`: the validated repository consumer is closed, but the other graph
consumers remain opaque.
