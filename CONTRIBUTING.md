# Contributing

Retirement Conductor handles consequential source changes. Contributions must
preserve evidence boundaries and refusal behavior, not only successful output.

## Before changing code or contracts

Read:

1. [Agent operating rules](AGENTS.md)
2. [Implementation goal](GOAL.md)
3. [Execution status](STATUS.md)
4. [Product definition](docs/PRODUCT.md)
5. [Build plan](PLAN.md)
6. the active [phase](docs/phases/README.md)
7. relevant [contracts](docs/CONTRACTS.md),
   [risks](docs/RISKS.md), and [decisions](docs/DECISIONS.md)

## Change process

1. State the product invariant or risk the change addresses.
2. Identify the authoritative source or observed behavior.
3. Add the smallest implementation that completely addresses it.
4. Add successful, refusal, and interruption coverage appropriate to the
   change.
5. Inspect generated evidence and public output.
6. Update contracts, decisions, risks, traceability, phase acceptance, and the
   evidence ledger when behavior changes.
7. Update `STATUS.md` only after inspecting the direct evidence.
8. Run `make check` and the phase-specific commands.

Release and compatibility changes must also follow the
[maintenance policy](docs/MAINTENANCE.md), update the executed
[compatibility matrix](docs/COMPATIBILITY.md), and rehearse the documented
[deployment lifecycle](docs/runbooks/DEPLOYMENT.md).

## Contract changes

A contract change must include:

- old and new schema versions;
- compatibility or migration behavior;
- a decision-log entry;
- positive and negative fixtures;
- replay behavior for existing campaigns;
- updated operator explanation.

Do not reuse a field with changed meaning.

## Adapter changes

An adapter contribution must:

- map DataHub evidence to an exact native identity;
- declare read, plan, apply, validate, and compensate capabilities;
- default to no mutation;
- pin source version and target scope before apply;
- use a documented native surface;
- compare actual targets with the approved plan;
- invoke a source-native validator;
- emit a strict receipt or a stable refusal;
- test retry, stale source, permission failure, scope expansion, partial
  failure, and compensation;
- distinguish live, fixture, and replay evidence.

## Evidence rules

- Store only redacted public-safe artifacts in version control.
- Address raw artifacts by digest and keep sensitive material outside Git.
- Record source version, capture time, scope, permissions, pagination,
  freshness, and limitations.
- Do not turn fixture behavior into a live claim.
- Do not turn ownership or acknowledgment into native validation.

## Pull request checklist

- [ ] The change advances a named phase or contains a justified contract fix.
- [ ] Product behavior and non-claims remain accurate.
- [ ] Successful and refusal paths are tested.
- [ ] Interrupted or repeated execution remains safe where applicable.
- [ ] No new dependency was added without a clear need and review.
- [ ] No credentials, private paths, raw SQL, or sensitive data are present.
- [ ] Documentation links and repository checks pass.
- [ ] Package, schema, compatibility, migration, and rollback claims agree.
- [ ] Risks and decisions match the observed result.
