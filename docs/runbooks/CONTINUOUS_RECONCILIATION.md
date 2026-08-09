# Continuous reconciliation and Retirement Lease revocation

This runbook observes one issued producer plan, presented to operators as a
Retirement Lease. The command rereads DataHub and Git/dbt through the existing
reconciliation boundary, reevaluates the canonical policy, republishes a
changed summary once, verifies read-back, and emits a versioned watch receipt.
It does not run a daemon or create another authorization store.

## Preconditions

The campaign must be `READY_TO_RETIRE`, its DataHub summary must have verified
read-back, and one unconsumed, unexpired producer plan must already be issued.
Use the same store path, writer identity, artifact directory, DataHub settings,
Git/dbt settings, and refresh receipt that produced the ready campaign.

Inspect the lease without changing state:

```bash
retirement-conductor campaign lease-status \
  --campaign "$RC_CAMPAIGN" \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER" \
  --artifact-dir "$RC_ARTIFACTS"
```

The projection is derived from the current canonical manifest, issued producer
plan, expiry, and gate-attempt ledger. Its statuses are `ISSUED`, `EXPIRED`,
`CONSUMED`, and `INVALIDATED`; no separate lease database exists.

## One-shot observation

Run the cron- and CI-safe watcher:

```bash
retirement-conductor campaign watch \
  --campaign "$RC_CAMPAIGN" \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER" \
  --artifact-dir "$RC_ARTIFACTS" \
  --refresh-receipt .retirement-conductor/datahub/seed-receipt.json \
  --once
```

The command holds the existing single-writer lock across the observation. A
durable `WATCH_OBSERVATION_RECORDED` event binds the attempt to the exact issued
plan and ready manifest before source reread. That observation grants no
authority, but its canonical event digest ensures the old lease is no longer
usable if the watcher is interrupted or DataHub becomes unavailable.

Exit codes are stable:

| Code | Result | Meaning |
|---:|---|---|
| 0 | `UNCHANGED` | Fresh equivalent evidence still yields readiness; the observed lease is nevertheless invalidated by the newer manifest |
| 3 | `REVERSED` | Fresh evidence changed the decision, such as a newly observed consumer |
| 4 | `PARTIAL` | Required evidence is partial, unknown, or stale |
| 5 | `UNAVAILABLE` | Required DataHub observation could not complete |
| 6 | `FAILED` | Reconciliation, publication, verification, or integrity checking failed |

The receipt is stored beneath
`$RC_ARTIFACTS/<campaign>/watch/<operation>/receipt.json`. It contains the
before/after manifest and evidence-envelope digests, source versions, result,
publication state, lease status, failure phase when applicable, and explicit
limitations.

## Retry and recovery

The operation identity is derived from the campaign and exact producer-plan
digest. A retry after reconciliation or publication interruption resumes from
the canonical event stream. It does not append a second observation,
reconciliation, publication, or verification event. If the write reached
DataHub but local recording was interrupted, exact read-back recovers the
write rather than repeating it.

An `UNAVAILABLE` or `PARTIAL` result is a safety outcome, not authorization to
reuse the old plan. Restore the required source, run an explicit fresh
reconciliation, publish and verify the new canonical summary, and issue a new
lease only if policy returns `READY_TO_RETIRE`.

Removing a disposable late lineage edge is not closure. Reconcile after the
removal and retain the consumer as unresolved until a native validation
receipt, verified removal, or proved non-applicability closes it.

## Scheduler boundary

An external scheduler may invoke the `--once` command. Do not run multiple
local writers, copy the SQLite database, place it on a shared filesystem, or
treat a scheduler trigger receipt as DataHub evidence. The source reread and
canonical campaign result are the acceptance boundary.

