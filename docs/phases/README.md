# Phase index

The phases are ordered by proof dependency. They are not estimates. A later
phase may start only when it can consume working artifacts from its
dependencies.

## Sequence

| File | Required outcome |
|---|---|
| [00 — Foundation](00-foundation.md) | Product contracts, package skeleton, promoted safety kernel, and deterministic fixture |
| [01 — Campaign kernel](01-campaign-kernel.md) | Durable, deterministic, resumable campaign behavior |
| [02 — DataHub evidence](02-datahub-evidence.md) | Bounded live inventory plus stable write/read-back |
| [03 — Git/dbt execution](03-git-dbt-execution.md) | Guarded native consumer mutation and validation |
| [04 — Reconciliation gate](04-reconciliation-gate.md) | Complete vertical with fresh rescan and enforceable refusal |
| [05 — Operator experience](05-operator-experience.md) | Understandable CLI and generated report backed by real state |
| [06 — Looker adapter](06-looker-adapter.md) | Second live heterogeneous native receipt |
| [07 — Security and reliability](07-security-reliability.md) | Adversarial safety, recovery, and least-privilege evidence |
| [08 — Deployment and adoption](08-deployment-adoption.md) | Repeatable installation, operation, evaluation, and maintenance |

## Required phase structure

Every phase defines:

- outcome;
- dependencies;
- scope and exclusions;
- deliverables;
- work breakdown;
- acceptance evidence;
- stop or reframe conditions;
- risks changed.

Deliverables are not complete merely because files exist. Acceptance evidence
must come from executed behavior and inspected artifacts.

## State vocabulary

- `active`: current implementation focus;
- `queued`: dependencies are not yet satisfied;
- `access-dependent`: independent work can complete, but live proof needs an
  external disposable boundary;
- `blocked`: a required current boundary is unavailable after independent work
  is exhausted;
- `complete`: all acceptance evidence exists and was inspected;
- `reframed`: the central hypothesis failed and the resulting boundary is
  recorded.

The authoritative state table is in [STATUS.md](../../STATUS.md). The proof
order remains in [PLAN.md](../../PLAN.md).
