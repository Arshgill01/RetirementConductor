# CP-01 PostgreSQL producer action integration notes

## Recommendation

`KEEP` the bounded action for CP-05 integration. Live-local PostgreSQL evidence
proved the exact quoted drop, separate principals, transaction-lock
preconditions, post-commit native verification, lost-response discovery,
replay refusal, and one-winner concurrency behavior. The result does not prove
production safety or general warehouse support.

## Branch boundary

- Exact base: `b8a839acd0b411d905fa0ed142838cd76ab618f4`
- Branch: `codex/cp-01-postgres-producer-action`
- Compose project: `rc_cp01_producer`
- Reserved endpoint: `127.0.0.1:25432`
- Shared gate, CLI, MCP, schemas, canonical documents, dependencies, and
  existing Make targets were not changed.

The public evidence index and exact tested behavior commit are recorded under
`artifacts/public/postgres-producer-action/`. Raw evidence remains ignored at
`.retirement-conductor/cp01/private/acceptance.json`.

## New integration surface

CP-05 should import only:

- `PostgresProducerSettings` and `PostgresTarget` from
  `retirement_conductor.postgres_producer_config`;
- `PostgresCliClient`, `PostgresProducerAction`, and
  `PostgresActionOutcome` from `retirement_conductor.postgres_producer`.

The module has no campaign authority. CP-05 must supply the already issued,
short-lived producer-plan expiry, the exact confirmed action digest, a unique
attempt ID, and trusted time. The gate ledger must record intent before calling
`apply` and must preserve `OUTCOME_UNKNOWN` as consumed authority.

## Smallest shared hunks CP-05 requires

Only CP-05 may make these changes:

1. Extend the producer-plan contract/schema with a versioned action binding
   for `postgres_drop_column_v1`, its target tuple, PostgreSQL/table identity,
   before-schema fingerprint, allowlist digest, expiry, and action digest.
2. Extend `gate.py` so the separately privileged producer process creates the
   mutation client only after every existing gate-time reread passes and the
   durable gate intent is recorded.
3. Map `COMMITTED`, `NOT_COMMITTED`, and `OUTCOME_UNKNOWN` into the existing
   gate ledger without treating a lost response as retryable. A prior unknown
   attempt must go through `resolve_outcome`, never `apply` again.
4. Add the narrow producer CLI surface and deployment preflight without
   exposing passwords, DSNs, arbitrary SQL, `CASCADE`, target overrides, or
   more than one action.
5. Add new stable shared refusal codes only if CP-05 needs to translate the
   task-local `POSTGRES_*` codes; preserve the task-local code in safe details.
6. Update architecture, contracts, decisions, risks, traceability, status, and
   evidence only after the integrated producer gate has passed live evidence.
7. Include the new source and runbook in package/release allowlists if the
   installed producer workflow is part of CP-05 acceptance.

No dependency or lockfile change is required. The implementation uses the
standard library plus `psql` from the pinned disposable PostgreSQL image.

## Integration invariants

- The campaign/agent process must not receive the mutation credential.
- The endpoint remains loopback-only for the recorded proof.
- Gate-time observation must bind database OID/version, relation OID, ordered
  columns, replacement facts, dependencies, principals, and allowlist digest.
- The action runs without `CASCADE` under an `ACCESS EXCLUSIVE` table lock and
  repeats the complete schema/dependency/permission checks inside the
  transaction.
- Post-commit observer reread must prove the legacy column absent and the exact
  replacement facts unchanged before CP-05 records `COMMITTED`.
- Replay or concurrency may produce only one committed destructive statement.
- Recovery is disposable database reconstruction, not column-value rollback.

## Validation and evidence

The final evidence-promotion commit records the exact commands, results,
versions, artifact digest, failure attempts, and clean-worktree status. CP-05
should rerun the direct acceptance command after merging, then exercise both a
gate refusal that leaves the column present and a clean integrated gate action
that removes it.
