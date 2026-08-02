# Execution status

This is the current implementation state. Update it after evidence is
inspected, not when work merely starts. `GOAL.md` defines the completion
contract; `PLAN.md` defines proof order.

## Current state

- Execution state: active under the DataHub-native reframe in `GOAL.md`
- Active phase: 06 — DataHub evidence-quality benchmark
- Baseline repository commit: `7d45b96a72222df5085f801bf35f66bcaf2496cd`
- Current external blocker: none for the overnight engineering goal; the
  independent-operator observation remains honest follow-on adoption evidence
- Next acceptance target: replace the abandoned Looker phase with a pinned
  official-dataset registry, deterministic field-retirement corpus, independent
  truth oracle, and live local DataHub Core benchmark
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
| 06 | active | former Looker work at `00db298` through `eb72067` is historical fixture/analysis evidence and no longer an acceptance dependency; the replacement contract is `docs/phases/06-data-quality-benchmark.md` | implement the official-dataset registry, deterministic synthetic truth corpus, live local DataHub evaluation, and zero-false-readiness refusal matrix |
| 07 | queued | credential-independent observations at `4fc5b2d`/`6feb1bc`; threat model, fault matrix, recovery, diagnostics, dependency audit, and scans | rerun and refresh security, fault, recovery, and evidence after the Looker surface is removed and the benchmark is integrated |
| 08 | queued | prior package observations at `eb72067`/`4411e8b`; clean installs, live Core reference, upgrade/rollback, backup, removal, and compatibility | rebuild and revalidate the release after Looker removal; independent operator evidence remains follow-on and must stay `NOT_RUN` until observed |

Allowed states are `queued`, `active`, `access-dependent`, `blocked`,
`complete`, and `reframed`. At most one phase is `active`. A phase can return
to `active` if later evidence invalidates its acceptance result.

## External boundary queue

| Boundary | Needed now | Current disposition | Controlling document |
|---|---|---|---|
| DataHub Core | no | agent may start a disposable local instance | `docs/ACCESS.md` |
| Git/dbt target | no | agent may create disposable local resources | `docs/ACCESS.md` |
| Official hackathon datasets | no | public CC0/public-domain inputs may be downloaded to an ignored cache only after revision, license, and checksum verification | `GOAL.md` |
| Looker | no | removed from the supported product and completion contract; do not provision, authenticate, ingest, query, or mutate it | `GOAL.md` |
| Independent operator | not for the overnight engineering goal | one prospective operator must still provide real adoption evidence before any customer-value claim | `docs/ACCESS.md` |

The current work is fully credential-independent. Do not substitute official
or generated fixtures for customer-value evidence, and do not reintroduce a
paid native integration merely to increase platform count.

## Update rule

Whenever a phase state changes:

1. link direct evidence in `docs/EVIDENCE_LEDGER.md`;
2. record the tested commit and evidence mode;
3. update changed risks and decisions;
4. name any remaining external boundary precisely;
5. run `make check`;
6. commit this file with the behavior and evidence it describes.
