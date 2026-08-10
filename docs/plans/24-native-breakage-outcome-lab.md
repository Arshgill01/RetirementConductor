# CP-04 — native downstream breakage outcome lab

## Objective

Create an independent disposable lab in which removing `legacy_status`
produces an actual, observable downstream failure. This converts the producer
decision from an internal gate result into a measured operational outcome.

## Product question

When an unsafe field retirement proceeds, does a real downstream workload
break for the exact reason Retirement Conductor was designed to prevent? When
the action is blocked, do native schema reread and workload execution prove the
incident was prevented?

## Required topology

Build a deterministic isolated environment with:

- PostgreSQL producer table
  `retirement_lab.orders(legacy_status, order_status, ...)`;
- compatible populated legacy and replacement values;
- one replacement-aware control workload;
- one legacy-field downstream workload running in a separate process or
  container and using a distinct read-only database principal;
- native schema and workload observation commands;
- deterministic full environment reconstruction.

Prefer an actual Apache Spark batch workload reading PostgreSQL through a
pinned JDBC boundary so the long-standing late Spark consumer story becomes a
native workload rather than metadata alone. Pin the Spark image and JDBC
driver version/checksum. If a reproducible Spark/JDBC boundary proves
technically impossible, retain the failed feasibility evidence and implement a
separate-container PostgreSQL client workload as a labeled fallback. The
fallback may prove generic downstream breakage but must not be called Spark.

Do not integrate DataHub or Retirement Conductor in this branch. CP-05 owns
the causal binding between this native workload, its DataHub identity, and the
three comparison arms.

## Deterministic data and workload contract

Freeze before running:

- generator version and seed;
- table DDL and ordered schema fingerprint;
- row count and safe whole-result digest;
- allowed status values and compatibility oracle;
- exact legacy and replacement workload definitions;
- expected pre-drop and post-drop outcomes;
- container image identities and native versions.

The public evidence must never contain raw rows. Record row count, schema,
result digest, error category, and exit code only.

The legacy workload must:

- execute successfully before the drop;
- select or transform `legacy_status` materially, not mention it in a comment;
- expose a stable safe output digest;
- fail after the exact drop with a normalized native
  `LEGACY_COLUMN_MISSING` outcome;
- succeed again only after deterministic environment reconstruction.

The replacement workload must succeed before and after the drop with the same
declared semantic digest or a predeclared equivalent result.

## Acceptance sequences

### Unsafe-action consequence

```text
seed producer
  → legacy workload succeeds
  → replacement workload succeeds
  → execute exact bounded DROP COLUMN
  → native schema reread proves legacy_status absent
  → legacy workload fails because the column is absent
  → replacement workload still succeeds
```

The test passes only if the failure is attributable to the missing exact field,
not networking, permissions, startup timing, or unrelated SQL errors.

### Prevented-action control

Provide a simple action-denied hook for CP-05, then prove:

```text
seed producer
  → do not execute DROP COLUMN
  → native schema reread proves legacy_status present
  → legacy workload remains healthy
  → replacement workload remains healthy
```

This branch does not decide why an action is denied. It only provides the
native observation needed to prove prevention.

### Reconstruction and isolation

- Recreate the environment after the destructive sequence.
- Prove the original schema and workload digests return exactly.
- Prove one run cannot observe another run's database or credentials.
- Stop and remove disposable services without deleting repository evidence.

## DataHub handoff artifact

Produce a public-safe native consumer descriptor CP-05 can ingest into
DataHub. It must bind:

- workload type and version;
- native job identity;
- producer dataset identity;
- exact `legacy_status` field usage;
- observed execution time and success digest;
- source code or job-definition digest;
- limitations and evidence mode.

The descriptor is not itself DataHub lineage evidence. CP-05 must ingest and
reread the corresponding DataHub aspect before using it in a campaign.

## Evidence

Create:

```text
artifacts/public/native-breakage-outcome-lab/
docs/runbooks/NATIVE_BREAKAGE_LAB.md
docs/plans/integration-notes-native-breakage-lab.md
```

The public index must include:

- frozen input digest;
- exact native component versions and image identities;
- before/after/reconstructed schema digests;
- legacy and replacement workload outcomes;
- normalized missing-column error evidence;
- destructive statement count;
- consumer descriptor digest;
- fallback classification if Spark was not achieved;
- explicit disposable/non-production limitation;
- canonical self-digest.

Retain raw service logs and native errors only under ignored runtime state.

## Owned files

Prefer isolated paths:

- `deploy/native-breakage-lab/`;
- `fixtures/native-breakage-lab/`;
- `scripts/run_native_breakage_lab.py`;
- `tests/unit/test_native_breakage_evidence.py`;
- `docs/runbooks/NATIVE_BREAKAGE_LAB.md`;
- `docs/plans/integration-notes-native-breakage-lab.md`;
- `artifacts/public/native-breakage-outcome-lab/`.

Do not edit product source, shared deployments, existing evidence, package
dependencies, or canonical documents.

## Validation

- Run the unsafe-action sequence from a clean environment at least twice.
- Run the prevented-action control.
- Verify deterministic reconstruction.
- Inspect public evidence for raw rows, credentials, paths, and unrestricted
  error text.
- Run focused tests and `make check`.

## Completion recommendation

Return one of:

- `KEEP_SPARK` — the pinned Spark workload provides reproducible native proof;
- `KEEP_GENERIC` — only the accurately labeled generic workload is reliable;
- `REMOVE` — the lab cannot attribute failure to the exact dropped field;
- `INCONCLUSIVE` — native evidence could not be completed.
