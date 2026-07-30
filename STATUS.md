# Execution status

This is the current implementation state. Update it after evidence is
inspected, not when work merely starts. `GOAL.md` defines the completion
contract; `PLAN.md` defines proof order.

## Current state

- Execution state: active
- Active phase: 06
- Baseline repository commit: `7d45b96a72222df5085f801bf35f66bcaf2496cd`
- Current external blocker: none
- Next acceptance target: verify the dedicated zero-cost Looker pre-trial
  boundary, then complete every credential-independent adapter contract,
  preflight, fixture, test, DataHub recipe, and refusal path without
  provisioning
- Last repository validation: phase 05 implementation at `ae62486` passed
  canonical CLI/report promotion, real-browser keyboard and responsive flows,
  two axe-core audits, UI tests, and public/secret scans; inspected artifacts
  were committed at `c213f33`; the closure worktree passed all 151
  `make check` tests plus Ruff, formatting, mypy, 112-file repository,
  secret, public-artifact, source/wheel build, and diff checks

## Phase ledger

| Phase | State | Direct evidence | Remaining boundary |
|---|---|---|---|
| 00 | complete | `EP-000` at `6692a3c`; strict schemas, 24 tests, eight refusal fixtures, clean wheel smoke test | none |
| 01 | complete | `EP-001` at `30173f1`; 85 tests, SQLite replay parity, interruption and refusal matrix | none |
| 02 | complete | `EP-002` at `19bebb9`; live Core resolved both fields, returned 31 consumers over seven pages, proved at least 30 beyond configured repository scope, and verified four updates to one document URN without lifecycle mutation | none |
| 03 | complete | `EP-003` at `3ca39a1`; exact live DataHub-to-dbt mapping, two one-file applies, native validation receipt, verified rollback, idempotent retry, and contained adversarial probes | none |
| 04 | complete | `EP-004` at `25466a9`; equivalent live reconciliation, verified stable publication, one issued-plan sentinel, live late-consumer reopening, rich-graph refusal, and adversarial gate matrix | no production warehouse deletion was attempted |
| 05 | complete | `EP-005` at `ae62486`; four-decision CLI, deterministic canonical reports, exact plan confirmation, structural public redaction, keyboard/mobile browser proof, and zero axe violations | independent nontechnical operation remains phase 08 evidence |
| 06 | active | deterministic predecessor plus the phase 04 canonical campaign outputs | zero-cost boundary handoff must be verified; live Looker instance/API evidence remains unavailable and provisioning is forbidden |
| 07 | queued | none | harden available paths, then close live Looker cases |
| 08 | queued | none | clean operation plus independent operator evidence |

Allowed states are `queued`, `active`, `access-dependent`, `blocked`,
`complete`, and `reframed`. At most one phase is `active`. A phase can return
to `active` if later evidence invalidates its acceptance result.

## External boundary queue

| Boundary | Needed now | Current disposition | Controlling document |
|---|---|---|---|
| DataHub Core | no | agent may start a disposable local instance | `docs/ACCESS.md` |
| Git/dbt target | no | agent may create disposable local resources | `docs/ACCESS.md` |
| Looker | preflight only; not yet live proof | dedicated zero-cost handoff queued for verification; `PROVISIONING_ALLOWED=false`, so no instance, IAM elevation, query, quota change, or paid resource may be created | `docs/ACCESS.md` |
| Independent operator | not until phase 08 proof | real human observation required | `docs/ACCESS.md` |

Do not turn a future access need into a current blocker. Complete every safe
independent path first.

## Update rule

Whenever a phase state changes:

1. link direct evidence in `docs/EVIDENCE_LEDGER.md`;
2. record the tested commit and evidence mode;
3. update changed risks and decisions;
4. name any remaining external boundary precisely;
5. run `make check`;
6. commit this file with the behavior and evidence it describes.
