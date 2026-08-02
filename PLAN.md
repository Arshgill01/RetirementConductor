# Build plan

This plan is ordered by proof dependency. Each phase must leave behind working
behavior and inspectable evidence; prose alone does not advance the product.
The continuous execution and completion rules are defined in
[GOAL.md](GOAL.md); live state is recorded in [STATUS.md](STATUS.md).

## Objective

Build a trustworthy control plane for one complete data-field retirement:

```text
retirement specification
  → bounded DataHub inventory
  → authorized Git/dbt migration
  → source-native validation
  → fresh graph reconciliation
  → durable campaign summary
  → producer-side readiness gate
```

The result must remain useful when the final answer is refusal. Honest
`BLOCKED`, `UNSAFE`, and `REVIEW_REQUIRED` outcomes are product behavior.

## Definition of the complete vertical

The first supported workflow is complete only when a user can:

1. Declare an exact legacy column, replacement column, evidence sources,
   consumer repository, required validators, and apply permissions.
2. Resolve the assets from live DataHub rather than predicted identifiers.
3. Traverse and fully page the configured downstream graph.
4. Compare graph evidence with repository and dbt evidence without pretending
   either source is complete.
5. Freeze the consumer inventory and all source fingerprints.
6. Create a minimal authorized branch change for a real dbt consumer.
7. Run the configured dbt parse, build, and test commands.
8. Re-ingest or refresh the relevant metadata and inventory again.
9. Reopen the campaign if a new consumer, changed source, incomplete evidence
   source, or failed validator appears.
10. Write a stable campaign summary to DataHub and read it back.
11. Produce a deterministic manifest and human-readable report from the same
    state.
12. Return a non-zero gate result unless policy yields `READY_TO_RETIRE`.
13. Prove both sides live locally: an isolated all-closed disposable campaign permits
    a harmless producer sentinel, and a rich graph with unresolved consumers
    refuses it.

No visual interface, paid native integration, or broad asset support
substitutes for this path.

## Dependency graph

```text
00 Foundation and evidence promotion
  └─ 01 Deterministic campaign kernel
       └─ 02 DataHub evidence boundary
            └─ 03 Git and dbt execution
                 └─ 04 Reconciliation and retirement gate
                      ├─ 05 Operator experience
                      └─ 06 DataHub evidence-quality benchmark
                           └─ 07 Security and reliability refresh
                                └─ 08 Deployment and adoption proof
```

Phases 05 and 06 may proceed independently only after phase 04 passes. Phase
07 refreshes the hardening evidence now that the benchmark has landed and the
deprecated adapter surface has been removed.

## Phase index

| Phase | Outcome | State |
|---|---|---|
| [00](docs/phases/00-foundation.md) | Proven experiment assets are promoted selectively and contracts become executable | see `STATUS.md` |
| [01](docs/phases/01-campaign-kernel.md) | Deterministic campaign policy, receipts, and durable state work without integrations | see `STATUS.md` |
| [02](docs/phases/02-datahub-evidence.md) | Live DataHub inventory and write/read-back produce bounded evidence | see `STATUS.md` |
| [03](docs/phases/03-git-dbt-execution.md) | One authorized Git/dbt consumer is changed and natively validated | see `STATUS.md` |
| [04](docs/phases/04-reconciliation-gate.md) | Fresh reconciliation and the producer-side refusal gate complete the vertical | see `STATUS.md` |
| [05](docs/phases/05-operator-experience.md) | CLI and generated report make the same engine understandable and operable | see `STATUS.md` |
| [06](docs/phases/06-data-quality-benchmark.md) | Official and synthetic truth sets stress DataHub evidence quality without false readiness | see `STATUS.md` |
| [07](docs/phases/07-security-reliability.md) | Least privilege, recovery, concurrency, and failure behavior withstand adversarial use | see `STATUS.md` |
| [08](docs/phases/08-deployment-adoption.md) | The product can be installed, operated, evaluated, and maintained by another team | see `STATUS.md` |

## Cross-cutting workstreams

### Product truth

- Keep [PRODUCT.md](docs/PRODUCT.md) aligned with observed behavior.
- Keep the evidence claim bounded and understandable without platform jargon.
- Treat direct competitors fairly and update
  [COMPETITIVE_BOUNDARY.md](docs/research/COMPETITIVE_BOUNDARY.md) when their
  documented capabilities change.

### Contracts

- Version retirement specifications, evidence envelopes, receipts, manifests,
  adapter behavior, and refusal codes.
- Change a contract only with a recorded decision and migration note.
- Do not sign or distribute an artifact whose provenance is not understood.

### Evidence

- Keep raw redacted observations separate from normalized claims.
- Record source version, time, scope, pagination, permissions, and freshness.
- Make every decision traceable to receipt and evidence identifiers.
- Never promote fixture evidence into a live claim.
- Maintain the phase and requirement mapping in
  [REQUIREMENTS_TRACEABILITY.md](docs/REQUIREMENTS_TRACEABILITY.md).
- Maintain tested commits, modes, artifacts, and limitations in
  [EVIDENCE_LEDGER.md](docs/EVIDENCE_LEDGER.md).

### Safety

- Separate read, plan, apply, validate, and final gate capabilities.
- Default to read and plan.
- Enforce exact source fingerprints and target allowlists at apply time.
- Keep producer mutation outside the general orchestration credential.

### Quality

- Test every permitted state transition and every refusal category.
- Test deterministic reruns and idempotent retries.
- Exercise failure after partial mutation and verify compensation.
- Validate the same artifacts that operators and the gate consume.

## Promotion rule

A phase moves to `complete` only when:

- every listed deliverable exists;
- every acceptance command succeeded;
- the produced artifacts were inspected;
- the negative cases behaved as specified;
- relevant risks and decisions were updated;
- the next phase can consume real outputs rather than stubs.

If a phase cannot satisfy its central product claim, follow its stop or reframe
condition. Do not bury the result under broader scope.

## Execution rule

Start with the active phase in [STATUS.md](STATUS.md), then continue through
every available phase under [GOAL.md](GOAL.md). A future access requirement
does not prevent credential-independent implementation, tests, packaging, or
fault work in later phases. Only direct acceptance evidence advances state.
