# Phase 01 — Deterministic campaign kernel

## Outcome

One campaign can be created, advanced, blocked, resumed, reconciled from
supplied evidence, and rebuilt deterministically after process interruption
without any external integration.

## Dependencies

- phase 00 schemas, vocabulary, fixtures, and package;
- accepted contracts in [CONTRACTS.md](../CONTRACTS.md).

## Scope

In scope:

- pure state-transition and policy functions;
- append-oriented SQLite events;
- materialized campaign state;
- consumer dispositions and receipt validation;
- approval and waiver records;
- attempts, retries, and idempotency;
- local campaign locking and overlap detection;
- manifest projection;
- restart and fault-injection tests.

Excluded:

- DataHub and native source clients;
- user management;
- distributed locks;
- general storage interface;
- asynchronous workers.

## Deliverables

- campaign and consumer state machines;
- SQLite schema and explicit migration mechanism;
- event types with versioned payloads;
- deterministic manifest projector;
- receipt validator;
- policy evaluator returning the four final decisions;
- stable refusal-code registry;
- campaign create, inspect, evaluate, resume, and export commands;
- state-transition, event-replay, integrity, and interruption tests.

## Work breakdown

1. Specify legal campaign and consumer transitions as data.
2. Make illegal transitions fail without writing an event.
3. Persist specification and policy digests at campaign creation.
4. Append inventory snapshots, plans, apply results, validations, and
   reconciliation snapshots as immutable events.
5. Project current state from the event stream.
6. Cache materialized state only after replay equivalence is proven.
7. Validate receipt mode, target set, source version, validator result, and
   expiration before changing disposition.
8. Bind approvals to campaign, plan digest, source version, targets, principal,
   and scope.
9. Keep waivers distinct from validation and require explicit policy.
10. Detect two active campaigns claiming the same native consumer identity.
11. Inject interruption before and after every event boundary.
12. Rebuild manifests from the database and compare canonical digests.

## Acceptance evidence

Required behavior:

- every legal transition succeeds and every illegal transition refuses;
- no exception or malformed receipt promotes state;
- fixture and replay receipts fail a live-required policy;
- missing, expired, wrong-scope, and wrong-plan approvals refuse;
- a newly supplied consumer changes a ready evaluation to unsafe;
- an allowed waiver is visible and a default-policy waiver remains blocking;
- two campaigns cannot enter apply for the same native identity;
- event replay and materialized state produce identical manifests;
- process interruption at each boundary resumes without duplicate transition
  or false readiness;
- corruption or digest mismatch produces `INTEGRITY_` refusal.

Required commands:

```bash
make check
pytest tests/unit tests/contracts tests/integration/test_campaign_store.py
retirement-conductor campaign replay fixtures/campaigns/blocked
retirement-conductor campaign evaluate fixtures/campaigns/blocked
git diff --check
```

Inspect:

- database migration;
- raw event sequence;
- replayed state;
- canonical manifest;
- refusal-code coverage report.

## Stop or reframe conditions

- If final decisions depend on model interpretation or mutable display text,
  stop and restore deterministic inputs.
- If SQLite cannot recover safely from controlled interruptions, fix the
  persistence model before adding integrations.
- If the common receipt cannot represent both the proven dbt behavior and the
  bounded Looker behavior, revise it before either adapter is built.

## Risks changed

- R-07 overlapping campaigns;
- R-12 transactional state;
- R-16 waiver bypass;
- R-18 idempotency;
- R-23 deterministic resume.
