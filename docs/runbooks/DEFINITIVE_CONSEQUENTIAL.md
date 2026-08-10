# Definitive consequential run

This runbook reproduces the live-local native comparison that integrates the
CP-01 PostgreSQL action, CP-02 Superset gate verifier, frozen CP-03 comparison,
and CP-04 Spark consequence workload.

## Safety boundary

The runner creates a fresh Compose project and fresh volumes for every arm.
PostgreSQL, Superset, and DataHub publish loopback ports only. Credentials are
generated at runtime and must never be copied into command arguments, logs, or
tracked files. Do not point this run at production services or replace the
pinned compose files with remote endpoints.

The producer observer cannot alter schema. A distinct mutator is created only
after durable one-use intent and is allowlisted to the exact disposable
`retirement_consequential.retirement_lab.orders.legacy_status` action. The
Superset gate principal can reread and execute the exact saved chart but cannot
update its dataset. Spark records normalized outcomes and safe digests, not
rows.

## Prerequisites

- Docker with Compose;
- `uv`, Git, bubblewrap, and GNU Make;
- `psql` on `PATH` (the accepted run used PostgreSQL client 18.4 against the
  pinned PostgreSQL 16 server);
- enough local capacity for pinned DataHub, Superset, PostgreSQL, and Spark
  images; and
- loopback ports 18080, 28088, 35432, and 8000 available. The runner pauses
  and later restores the known disposable projects using 18080/18088.

Verify the branch is based on the required planning commit and has no local
source changes before the evidence run:

```bash
git merge-base --is-ancestor 7a7908f HEAD
git status --short
```

## Run

First verify that the frozen CP-03 inputs are unchanged:

```bash
uv run python scripts/run_realistic_alternative_ablation_v2.py verify-freeze
```

Then run all arms from independently reconstructed environments:

```bash
uv run python scripts/run_definitive_consequential.py run
```

The command is intentionally long-running. It must complete these arms in
order:

1. clean Retirement Conductor action and replay refusal;
2. late-consumer prevention;
3. unsafe point-in-time static consequence;
4. fair fresh-CI late-consumer refusal;
5. negative native-boundary matrix; and
6. crash/lost-response recovery matrix.

Do not retry an `OUTCOME_UNKNOWN` plan. The recovery arm must use the explicit
native resolve operation and retain one execute call.

Expected terminal result:

```text
DEFINITIVE_CONSEQUENTIAL_RUN_COMPLETE: classification=NO_MATERIAL_ADVANTAGE recommendation=SIMPLIFY
```

## Inspect and verify

Inspect the public facts rather than trusting the exit status:

```bash
jq . artifacts/public/definitive-consequential-run/comparison.json
jq . artifacts/public/definitive-consequential-run/retirement-conductor-clean.json
jq . artifacts/public/definitive-consequential-run/retirement-conductor-late.json
jq . artifacts/public/definitive-consequential-run/point-in-time-static.json
jq . artifacts/public/definitive-consequential-run/fresh-ci-equivalent.json
jq . artifacts/public/definitive-consequential-run/retirement-conductor-negative-matrix.json
jq . artifacts/public/definitive-consequential-run/retirement-conductor-recovery-matrix.json
uv run python scripts/run_definitive_consequential.py verify
```

Required invariants:

- clean action committed exactly one statement, removed only the legacy
  column, preserved the replacement, and refused replay;
- product late and fresh CI each committed zero with exact five-consumer
  DataHub membership;
- static committed one and the legacy Spark workload returned SQLSTATE `42703`
  while the replacement workload succeeded;
- every negative case retained the legacy column;
- crash-before-client is `NOT_COMMITTED` with zero attempted statements;
- lost response is first `OUTCOME_UNKNOWN`, then resolved from native state
  without a second execute; and
- the index, every arm digest, the frozen input hashes, implementation commit,
  image versions, limitations, and `NO_MATERIAL_ADVANTAGE` classification
  verify offline.

Finally run repository validation:

```bash
make check
git diff --check
```

## Cleanup and recovery

Each arm tears down its containers and volumes in a `finally` block. The
runner also restores any known disposable projects it paused. After success or
failure, confirm no CP-05 project remains:

```bash
docker ps --format '{{.Names}}' | rg '^rc_cp05_' || true
```

Private runtime state remains ignored under
`.retirement-conductor/definitive-consequential-run/` for diagnosis. It is not
public evidence and may contain machine-specific paths. The tracked public
bundle is intentionally row-free, credential-free, and independently
verifiable.

## Interpretation

The result says that fresh action-time verification matters and static
reusable authority is unsafe. It does not show that persistent lease machinery
is materially safer than competent fresh CI. Prefer the simpler fresh-CI
protocol when it can hold the same boundaries; use the Retirement Lease only
for a demonstrated need for durable handoff, recovery, or causal audit.
