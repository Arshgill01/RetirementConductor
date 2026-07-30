# Execution status

This is the current implementation state. Update it after evidence is
inspected, not when work merely starts. `GOAL.md` defines the completion
contract; `PLAN.md` defines proof order.

## Current state

- Execution state: active
- Active phase: none; phases 06 through 08 are access-dependent
- Baseline repository commit: `7d45b96a72222df5085f801bf35f66bcaf2496cd`
- Current external blocker: the live disposable Looker boundary needed by
  `EP-006`/the Looker-specific portion of `EP-007`, and one real independent
  operator needed by `EP-008`; all safe credential-independent work is
  complete
- Next acceptance target: run the generated no-secret Looker preflight against
  one user-approved pre-existing disposable instance and record one
  independent operator using the published Core evaluation workflow
- Last repository validation: behavior commit `eb72067` passed all 228 tests,
  Ruff, formatting, strict mypy, repository validation, secret and public
  artifact scans, both package builds, and `git diff --check`; the complete
  Phase 08 command set then passed, and seven inspected public-safe artifacts
  were committed at `4411e8b`

## Phase ledger

| Phase | State | Direct evidence | Remaining boundary |
|---|---|---|---|
| 00 | complete | `EP-000` at `6692a3c`; strict schemas, 24 tests, eight refusal fixtures, clean wheel smoke test | none |
| 01 | complete | `EP-001` at `30173f1`; 85 tests, SQLite replay parity, interruption and refusal matrix | none |
| 02 | complete | `EP-002` at `19bebb9`; live Core resolved both fields, returned 31 consumers over seven pages, proved at least 30 beyond configured repository scope, and verified four updates to one document URN without lifecycle mutation | none |
| 03 | complete | `EP-003` at `3ca39a1`; exact live DataHub-to-dbt mapping, two one-file applies, native validation receipt, verified rollback, idempotent retry, and contained adversarial probes | none |
| 04 | complete | `EP-004` at `25466a9`; equivalent live reconciliation, verified stable publication, one issued-plan sentinel, live late-consumer reopening, rich-graph refusal, and adversarial gate matrix | no production warehouse deletion was attempted |
| 05 | complete | `EP-005` at `ae62486`; four-decision CLI, deterministic canonical reports, exact plan confirmation, structural public redaction, keyboard/mobile browser proof, and zero axe violations | independent nontechnical operation remains phase 08 evidence |
| 06 | access-dependent | `00db298`, `3435177`, `5454594`, `a57b06e`, `e6183d1`, `9380815`, `e128e20`, `813bf20`, and `eb72067`; deterministic API 4.0 lifecycle, durable intent recovery, campaign binding, exact LookML ingestion into local DataHub, official recipe validation, campaign-safe no-secret resume packet, reconciliation, and an inspected non-live evidence bundle; 228 tests pass | one pre-existing user-approved disposable Looker instance/API plus live saved-Look ingestion, exact campaign bootstrap, native query, compensation, delete/recreate, and lost-response evidence; fixture and local LookML results do not satisfy `EP-006` |
| 07 | access-dependent | credential-independent EP-007 observations at `4fc5b2d`/`6feb1bc`; threat model, plan-only receipts, fault matrix, online backup/restore, copied-store refusal, diagnostics, dependency audit, secret scan, and five inspected public artifacts | phase 07 cannot close until EP-006 supplies live Looker permission, fault, retry, unknown-outcome, compensation, and concurrency evidence |
| 08 | access-dependent | credential-independent EP-008 observations at `eb72067`/`4411e8b`; reproducible 0.2.0 wheel/source archive, four clean Python installs, actionable preflight, live installed-wheel Core reference, upgrade/rollback, backup, copied-state refusal, confirmed state removal, uninstall, compatibility matrix, and seven inspected public artifacts | one independent prospective operator must execute the runbook and provide redacted frequency, friction, value, willingness, and buyer evidence; `EP-008` remains not-run |

Allowed states are `queued`, `active`, `access-dependent`, `blocked`,
`complete`, and `reframed`. At most one phase is `active`. A phase can return
to `active` if later evidence invalidates its acceptance result.

## External boundary queue

| Boundary | Needed now | Current disposition | Controlling document |
|---|---|---|---|
| DataHub Core | no | agent may start a disposable local instance | `docs/ACCESS.md` |
| Git/dbt target | no | agent may create disposable local resources | `docs/ACCESS.md` |
| Looker | yes | the generated packet requires one user-approved pre-existing disposable instance and values placed only in ignored local configuration; dedicated pretrial state still has zero instances, so no API preflight can run; `PROVISIONING_ALLOWED=false` forbids instance creation, IAM elevation, queries, quota changes, and paid resources | `docs/ACCESS.md` |
| Independent operator | yes | install, deployment, evaluation, compatibility, and observation materials are ready; one prospective operator independent of the author must run the safe workflow and provide a redacted observation | `docs/ACCESS.md` |

No safe credential-independent acceptance task remains. Keep the Codex goal
active and resume immediately when either external boundary is supplied; do
not substitute author operation, fixture evidence, or new provisioning.

## Update rule

Whenever a phase state changes:

1. link direct evidence in `docs/EVIDENCE_LEDGER.md`;
2. record the tested commit and evidence mode;
3. update changed risks and decisions;
4. name any remaining external boundary precisely;
5. run `make check`;
6. commit this file with the behavior and evidence it describes.
