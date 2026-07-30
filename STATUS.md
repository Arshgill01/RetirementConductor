# Execution status

This is the current implementation state. Update it after evidence is
inspected, not when work merely starts. `GOAL.md` defines the completion
contract; `PLAN.md` defines proof order.

## Current state

- Execution state: active
- Active phase: 08
- Baseline repository commit: `7d45b96a72222df5085f801bf35f66bcaf2496cd`
- Current external blocker: none
- Next acceptance target: complete and inspect every credential-independent
  phase 08 package, clean-install, preflight, reference-campaign, upgrade,
  rollback, backup, removal, compatibility, and single-writer case before
  requesting the remaining live Looker and independent-operator boundaries
- Last repository validation: phase 07 behavior commit `4fc5b2d` passed
  217 tests under `make check`; focused security, fault, and recovery targets
  passed 93, 72, and 43 tests; the security scan audited 18 resolved packages
  with zero known vulnerabilities; canonical recovery and capability evidence
  was inspected and committed at `6feb1bc`

## Phase ledger

| Phase | State | Direct evidence | Remaining boundary |
|---|---|---|---|
| 00 | complete | `EP-000` at `6692a3c`; strict schemas, 24 tests, eight refusal fixtures, clean wheel smoke test | none |
| 01 | complete | `EP-001` at `30173f1`; 85 tests, SQLite replay parity, interruption and refusal matrix | none |
| 02 | complete | `EP-002` at `19bebb9`; live Core resolved both fields, returned 31 consumers over seven pages, proved at least 30 beyond configured repository scope, and verified four updates to one document URN without lifecycle mutation | none |
| 03 | complete | `EP-003` at `3ca39a1`; exact live DataHub-to-dbt mapping, two one-file applies, native validation receipt, verified rollback, idempotent retry, and contained adversarial probes | none |
| 04 | complete | `EP-004` at `25466a9`; equivalent live reconciliation, verified stable publication, one issued-plan sentinel, live late-consumer reopening, rich-graph refusal, and adversarial gate matrix | no production warehouse deletion was attempted |
| 05 | complete | `EP-005` at `ae62486`; four-decision CLI, deterministic canonical reports, exact plan confirmation, structural public redaction, keyboard/mobile browser proof, and zero axe violations | independent nontechnical operation remains phase 08 evidence |
| 06 | access-dependent | `00db298`, `3435177`, `5454594`, `a57b06e`, `e6183d1`, `9380815`, and `e128e20`; deterministic API 4.0 lifecycle, durable intent recovery, campaign binding, exact LookML ingestion into local DataHub, official recipe validation, no-secret access packet, reconciliation, and an inspected non-live evidence bundle; 188 tests pass | one pre-existing user-approved disposable Looker instance/API plus live saved-Look ingestion, native query, compensation, delete/recreate, and lost-response evidence; fixture and local LookML results do not satisfy `EP-006` |
| 07 | access-dependent | credential-independent EP-007 observations at `4fc5b2d`/`6feb1bc`; threat model, plan-only receipts, fault matrix, online backup/restore, copied-store refusal, diagnostics, dependency audit, secret scan, and five inspected public artifacts | phase 07 cannot close until EP-006 supplies live Looker permission, fault, retry, unknown-outcome, compensation, and concurrency evidence |
| 08 | active | phase contract under implementation | finish every clean-machine and deployment task; independent operation and value evidence then require a real prospective operator |

Allowed states are `queued`, `active`, `access-dependent`, `blocked`,
`complete`, and `reframed`. At most one phase is `active`. A phase can return
to `active` if later evidence invalidates its acceptance result.

## External boundary queue

| Boundary | Needed now | Current disposition | Controlling document |
|---|---|---|---|
| DataHub Core | no | agent may start a disposable local instance | `docs/ACCESS.md` |
| Git/dbt target | no | agent may create disposable local resources | `docs/ACCESS.md` |
| Looker | no; safe independent phase work remains | dedicated pretrial check verified zero instances, unallocated trial/paid quota, zero BigQuery query quota, and zero stored bytes; this is read-only GCP state, not Looker acceptance; `PROVISIONING_ALLOWED=false` forbids instance creation, IAM elevation, queries, quota changes, and paid resources | `docs/ACCESS.md` |
| Independent operator | no; credential-independent phase 08 work remains | real human observation is required after the reproducible evaluation path is ready | `docs/ACCESS.md` |

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
