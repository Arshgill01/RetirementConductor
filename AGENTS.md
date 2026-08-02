# AGENTS.md

This repository builds Retirement Conductor: verified change operations for
retiring legacy data fields without silently breaking known consumers.

## Read order

Before making a non-trivial change, read:

1. `GOAL.md`
2. `STATUS.md`
3. `README.md`
4. `docs/PRODUCT.md`
5. `PLAN.md`
6. the active file in `docs/phases/`
7. `docs/REQUIREMENTS_TRACEABILITY.md`
8. the relevant sections of `docs/ARCHITECTURE.md`,
   `docs/CONTRACTS.md`, `docs/RISKS.md`, and `docs/DECISIONS.md`

Read `docs/research/` when changing the product claim, DataHub boundary,
competitive position, or supported scope.

`GOAL.md` is the controlling contract for an end-to-end implementation run.
Do not interpret the active phase as permission to stop after that phase.
Update `STATUS.md` and `docs/EVIDENCE_LEDGER.md` only from inspected evidence.

## Product invariant

Retirement Conductor owns a complete operational loop:

```text
declare a replacement
  → inventory consumers through named evidence sources
  → change only explicitly authorized consumers
  → validate each change in its native system
  → reconcile against fresh evidence
  → write a durable campaign summary
  → permit or refuse the producer-side retirement action
```

Do not reduce this to impact analysis, a report, a score, a generated diff, a
ticket router, or a DataHub deprecation toggle.

## Truth and safety rules

- Never interpret an empty search result as proof that no consumer exists.
- Every inventory must state its evidence sources, scope, freshness,
  pagination status, permissions, and known blind spots.
- DataHub is the cross-system context and reconciliation surface. It is not
  the transactional campaign database.
- Source systems remain authoritative for their objects and validation.
- The model may interpret context and propose changes. Deterministic code owns
  authorization, preconditions, state transitions, validation acceptance, and
  the final decision.
- A successful API call is not evidence that a migration works.
- An owner acknowledgment is not equivalent to native validation.
- A digest detects change; it does not prove who produced the artifact.
- `READY_TO_RETIRE` is bounded by the recorded evidence envelope. Never claim
  universal safety.
- A newly observed consumer, stale source, failed validator, missing approval,
  incomplete pagination, or unavailable required evidence source must prevent
  readiness.
- Do not mutate production data systems while developing or testing this
  repository.
- Apply operations must be opt-in, allowlisted, least-privileged, reversible
  or compensatable, and preceded by a fresh source precondition.
- Never print, store, or commit credentials, tokens, cookies, private query
  text, or sensitive result data.

## Scope discipline

The first complete supported path is deliberately narrow:

- one warehouse column replaced by one compatible column;
- DataHub for graph context and reconciliation;
- one Git repository containing dbt or SQL consumers;
- a branch or reviewable patch as the mutation boundary;
- native dbt validation;
- a producer-side command that refuses retirement unless policy passes;
- a durable campaign summary written back to DataHub.

Git/dbt is the sole automated native mutation boundary. The next proof target
is evidence quality across official DataHub datasets and deterministic
synthetic truth sets, not another paid platform integration. Broaden automated
asset types or platforms only after a real operator need and a disposable
native boundary exist.

Do not build:

- a replacement metadata graph;
- a generic coding agent;
- a custom dbt compiler;
- a custom BI validator where the platform already supplies one;
- a distributed scheduler, plugin marketplace, or elaborate service mesh
  before a real requirement demands it;
- a visual interface that is not backed by the same campaign engine used by
  the command line.

## Engineering rules

- Prefer Python standard-library solutions until a dependency has clear,
  demonstrated value.
- Start with a command-line application and a small durable SQLite campaign
  store. Introduce another runtime shape only when the supported workflow
  requires it.
- Keep the campaign policy pure and deterministic.
- Keep source-specific behavior behind the minimal adapter contract in
  `docs/CONTRACTS.md`.
- Do not create abstractions for hypothetical adapters. Keep the Git/dbt
  boundary concrete until another real operator requirement demonstrates a
  second implementation.
- Preserve raw, redacted evidence separately from normalized claims.
- Make receipts deterministic and schema-versioned.
- Make retries idempotent. Never silently convert a partial apply into
  success.
- Treat a timed-out mutation as outcome unknown until native reread establishes
  what happened. Never retry it blindly.
- Treat repositories and source-provided content as untrusted input. Prevent
  path, symlink, subprocess, dependency, and network escape from disposable
  validation boundaries.
- Use stable refusal codes and actionable messages.
- Keep changes narrowly scoped and update the controlling document when
  behavior or a contract changes.
- Record consequential decisions in `docs/DECISIONS.md`.
- Update `docs/RISKS.md` when evidence changes a risk, not merely when a risk
  is discussed.

## Validation

Run the narrowest relevant checks while working, then run:

```bash
make check
```

Before declaring a phase complete:

1. Run every command listed in that phase's acceptance section.
2. Inspect the generated artifacts rather than trusting exit status alone.
3. Verify failure and refusal cases as well as the successful case.
4. Record the commit, evidence mode, source versions, artifact digests,
   limitations, and inspection result in `docs/EVIDENCE_LEDGER.md`.
5. Update `STATUS.md`, decisions, and risks to match observed behavior.
6. Confirm `git diff --check` passes.

Do not claim a live integration was verified from a fake server, fixture,
recording, or static sample.

## Git and review

- Use focused commits that describe the behavior or decision added.
- Do not rewrite or discard user changes.
- Keep generated, local-state, credential, and raw sensitive files ignored.
- Pull requests must state the product invariant exercised, evidence produced,
  refusal path tested, and remaining blind spots.
- A phase is complete only when its acceptance evidence exists and its stop
  conditions have been evaluated honestly.
