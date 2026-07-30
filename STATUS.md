# Execution status

This is the current implementation state. Update it after evidence is
inspected, not when work merely starts. `GOAL.md` defines the completion
contract; `PLAN.md` defines proof order.

## Current state

- Execution state: active
- Active phase: 01
- Baseline repository commit: `7d45b96a72222df5085f801bf35f66bcaf2496cd`
- Current external blocker: none
- Next acceptance target: deterministic campaign state, SQLite replay, policy,
  interruption recovery, and manifest digest parity
- Last repository validation: phase 00 acceptance passed at
  `6692a3ca20db61766bc109353fccfafb2db27b1f`

## Phase ledger

| Phase | State | Direct evidence | Remaining boundary |
|---|---|---|---|
| 00 | complete | `EP-000` at `6692a3c`; strict schemas, 24 tests, eight refusal fixtures, clean wheel smoke test | none |
| 01 | active | phase 00 event and manifest contracts | implement and run phase acceptance |
| 02 | queued | prior experiment baseline only | implement against disposable Core |
| 03 | queued | prior experiment baseline only | implement product adapter and live disposable run |
| 04 | queued | none | phases 02 and 03 |
| 05 | queued | none | canonical phase 04 manifests |
| 06 | access-dependent | deterministic predecessor only | disposable Looker instance and scoped access |
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
| Looker | not until live phase 06 proof | user-provided disposable scope required | `docs/ACCESS.md` |
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
