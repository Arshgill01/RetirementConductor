# WS-03 — continuous reconciliation and Retirement Lease revocation

## Objective

Turn late-consumer reversal from a scripted campaign step into a real product
behavior. A ready campaign should remain under fresh observation, and an
actual DataHub graph or evidence change should invalidate its short-lived
producer authorization before another producer action can occur.

The existing one-use producer plan already has most Retirement Lease
semantics. This workstream should expose and exercise those semantics rather
than build a second authorization system.

## Product result

```text
READY campaign
  -> publish and verify DataHub summary
  -> issue short-lived Retirement Lease
  -> watch the declared evidence envelope
  -> DataHub observes a new consumer or stale/partial source
  -> normal reconciliation rebuilds canonical state
  -> old lease no longer matches the manifest
  -> DataHub summary records the reversed decision
  -> producer gate refuses
```

## Runtime shape

Start with a deterministic `--once` watcher operation. It must be safe to run
from cron, CI, or an external scheduler. Add a bounded interval loop only if
shutdown, locking, retry, and observability remain simple.

The watcher:

1. acquires the existing single-writer boundary;
2. loads the canonical campaign and recorded evidence envelope;
3. confirms the campaign is eligible for observation;
4. rereads equivalent DataHub and native state through existing adapters;
5. records the normal reconciliation event, never a watcher-specific policy
   override;
6. evaluates the same deterministic policy;
7. publishes the changed summary once and verifies read-back when configured;
8. records a small watch receipt containing before/after manifest digests,
   observed source versions, result, and limitations;
9. exits with a stable code that distinguishes unchanged, reversed, partial,
   unavailable, and failed observations.

Do not build a distributed scheduler or background service. DataHub Actions or
metadata events may trigger the command later, but the acceptance boundary is
the source reread and canonical result, not the trigger transport.

## Retirement Lease projection

Use “Retirement Lease” as the user-facing name for the existing producer plan
only when the behavior remains exact:

- bound to one campaign, manifest, evidence envelope, publication, producer
  source, trusted run, action, and expiry;
- maximum lifetime remains bounded;
- at most one exact issued plan per canonical manifest;
- one use;
- not transferable;
- stale when the campaign manifest changes;
- consumed on an outcome-unknown producer attempt;
- never issued for `BLOCKED`, `REVIEW_REQUIRED`, or `UNSAFE`.

The operator view should project `ISSUED`, `EXPIRED`, `CONSUMED`, or
`INVALIDATED` from canonical records. It must not create a second mutable lease
database. If a new durable event is required, it must record observation, not
grant authority.

## Live acceptance

The live test must not append a consumer directly to campaign state.

1. Run the complete isolated campaign to `READY_TO_RETIRE`.
2. Publish and verify the DataHub summary.
3. Issue one short-lived Retirement Lease and preserve its exact bytes.
4. Through a supported DataHub metadata API or ingestion job, add a new exact
   field-level consumer inside the declared traversal scope.
5. Verify the new entity and edge are readable from DataHub independently of
   Retirement Conductor.
6. Run the watcher with `--once`.
7. Confirm the campaign becomes `UNSAFE` with the correct new-consumer
   evidence.
8. Confirm publication read-back exposes the reversed decision.
9. Attempt the preserved lease and prove deterministic refusal before any
   second producer sentinel.
10. Remove the disposable graph edge, reingest, and demonstrate the documented
    recovery path without pretending that disappearance alone validates the
    consumer.

Also exercise:

- partial pagination;
- DataHub unavailable;
- stale source-native data with recent metadata ingestion;
- changed principal or source scope;
- watcher interruption after observation but before publication;
- concurrent watcher attempts;
- expired lease;
- consumed lease;
- outcome-unknown prior gate attempt.

## Suggested implementation ownership

Prefer new files:

- `src/retirement_conductor/watch.py`;
- `schemas/watch-receipt-v1.schema.json`;
- focused unit, integration, reliability, and live-local acceptance tests;
- one runbook and public evidence generator.

Changes to `cli.py`, `agent.py`, `agent_mcp.py`, `store.py`, `events.py`,
`gate.py`, `operator.py`, `schemas.py`, and `Makefile` must remain narrow. The
watcher must call existing reconciliation and publication operations rather
than copy their logic.

## Agent surface

Expose read-only lease status and a bounded “reconcile now” operation. The
model may explain or request a watch operation, but it cannot mark a lease
valid, prevent invalidation, change the evidence envelope, or reuse an older
green manifest.

## Public evidence

Publish:

- ready manifest and issued lease digests;
- DataHub write receipt for the late consumer;
- independent DataHub reread proving the consumer exists;
- watch receipt and before/after manifest digests;
- verified DataHub summary read-back;
- refused old-lease gate receipt;
- producer sentinel count before and after;
- exact source versions, timing, limitations, and evidence mode.

## Stop conditions

Do not ship if:

- the watcher contains policy logic separate from `policy.py`;
- it mutates a campaign to force invalidation;
- trigger receipt is substituted for a DataHub reread;
- an old lease can execute after manifest change;
- publication failure is silently ignored;
- retries can duplicate reconciliation or publication events;
- a long-running daemon is required for the acceptance path.
