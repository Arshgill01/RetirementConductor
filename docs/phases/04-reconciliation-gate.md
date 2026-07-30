# Phase 04 — Reconciliation and producer-side gate

## Outcome

The complete supported vertical runs from declaration through a fresh DataHub
rescan, durable summary, and enforceable producer-side decision. New, stale,
failed, or unresolved consumers prevent the producing change.

## Dependencies

- phase 02 DataHub evidence boundary;
- phase 03 live Git/dbt receipt;
- disposable metadata refresh path;
- representative producer migration command or CI fixture.

## Scope

In scope:

- metadata refresh or re-ingestion for changed dbt state;
- before/after graph snapshots;
- consumer membership and identity comparison;
- receipt freshness and invalidation;
- late-consumer detection;
- stable DataHub summary update and read-back;
- canonical manifest generation;
- producer-side gate command;
- full end-to-end success and refusal scenarios.

Excluded:

- direct warehouse field deletion by the general campaign process;
- ignoring known unsupported external consumers to force readiness;
- considering a graph edge disappearance sufficient closure;
- separate policy logic in CI.

## Deliverables

- reconciliation engine;
- snapshot-diff format;
- evidence refresh and expiry policy;
- late-consumer and stale-receipt handling;
- stable campaign publication;
- `retirement-conductor gate` command;
- representative producer workflow integration;
- end-to-end disposable environment and runbook;
- canonical manifest and public-safe report data.

## Work breakdown

1. Freeze the baseline graph and inventory digests.
2. Attach the validated Git/dbt receipt.
3. Refresh the relevant DataHub metadata source.
4. Wait through a bounded, observable indexing condition rather than an
   unbounded sleep.
5. capture a fresh graph snapshot with the same declared scope.
6. Compare consumers by stable identity and evidence provenance.
7. Invalidate receipts whose source or native identity changed.
8. Add every newly observed consumer as a blocker.
9. Keep disappeared consumers unresolved unless separately closed.
10. Evaluate policy and write the updated summary to DataHub.
11. Read back and verify manifest, blockers, and evidence-envelope digests.
12. Invoke the gate from a representative producer change.
13. Exercise a live isolated DataHub and Git/dbt campaign in which every
    observed consumer closes and readiness permits one harmless producer
    sentinel.
14. Exercise a live rich-graph refusal where external consumers remain.
15. Exercise all four decisions through deterministic fixtures.
16. Introduce a late consumer after apparent readiness and verify reopening.
17. Change source after validation and verify gate refusal.
18. Change replacement schema, policy, validator configuration, or
    authorization after validation and verify gate refusal.
19. Exercise missing local state, unavailable DataHub read-back, tampered
    artifacts, and an untrusted producer-run context.
20. Bind the gate to one exact harmless producer plan and trusted invocation;
    attempt replay, delayed use, and a different plan.

## Acceptance evidence

Required behavior:

- before and after snapshots use equivalent declared scope;
- refresh and indexing status are observable and bounded;
- new consumer reopens the campaign;
- changed consumer source invalidates its receipt;
- disappeared edge without closure remains blocking;
- required evidence becoming stale or partial blocks;
- DataHub summary and local manifest agree after read-back;
- representative unresolved external consumers yield `UNSAFE`;
- missing required access yields `BLOCKED`;
- a declared semantic decision yields `REVIEW_REQUIRED`;
- a live isolated all-closed, fresh campaign yields `READY_TO_RETIRE`;
- a live rich graph with unresolved external consumers yields `UNSAFE`;
- the producer workflow executes its harmless sentinel only for the live ready
  result and executes no producer step for non-ready outcomes;
- the gate uses the same policy output as the CLI and report;
- gate decision is recorded with the exact manifest digest.
- table-level evidence is never promoted into field-level closure;
- replacement, policy, configuration, validator, and authorization drift
  invalidate readiness;
- missing campaign state, failed publication verification, tampered evidence,
  or untrusted execution provenance makes the gate non-zero.
- a green result cannot be reused, delayed, or applied to a different producer
  plan, campaign writer, or source version.

Required commands:

```bash
make check
retirement-conductor campaign reconcile --campaign <id>
retirement-conductor campaign publish --campaign <id>
retirement-conductor campaign verify-publication --campaign <id>
retirement-conductor gate --campaign <id>
make test-end-to-end
git diff --check
```

Inspect:

- baseline and reconciliation snapshots;
- diff and invalidated receipts;
- canonical manifest;
- DataHub read-back;
- producer workflow logs for allowed and refused cases.

## Stop or reframe conditions

- If the graph cannot be refreshed or scoped consistently, readiness remains
  unavailable; do not compare incomparable snapshots.
- If a producer workflow cannot enforce the gate, describe the output as an
  advisory decision and revisit the product claim.
- If reconciliation is dominated by false identity changes, fix identity
  normalization before adding adapters.

## Risks changed

- R-01 coverage;
- R-04 late consumer;
- R-09 complete product loop;
- R-17 disappearing edge;
- R-20 producer bypass;
- R-23 resume across full workflow;
- R-30 replacement drift;
- R-32 evidence granularity;
- R-33 executable-input drift;
- R-34 gate provenance and availability;
- R-35 gate-to-action race.
