# Execution status

This is the current implementation state. Update it after evidence is
inspected, not when work merely starts. `GOAL.md` defines the completion
contract; `PLAN.md` defines proof order.

## Current state

- Execution state: active under the DataHub-native reframe in `GOAL.md`
- Active phase: 06 — DataHub evidence-quality benchmark
- Current benchmark behavior commit: `34df09e`
- Current external blocker: none for the overnight engineering goal; the
  independent-operator observation remains honest follow-on adoption evidence
- Next acceptance target: remove the deprecated Looker release surface, then
  rerun security, fault, recovery, package, install, upgrade, and reference
  acceptance against the narrowed product
- Last repository validation: benchmark behavior commit `34df09e` passed 242
  tests, Ruff, formatting, strict mypy, 187-file repository validation, a
  322-file secret scan, the 56-file public-artifact review, source and wheel
  builds, and `git diff --check`; two full live runs matched semantic digest
  `sha256:c60c2a91bc5202f794357052833598e1bd824200ffe047f2b51d1b77f6d3ed54`

## Phase ledger

| Phase | State | Direct evidence | Remaining boundary |
|---|---|---|---|
| 00 | complete | `EP-000` at `6692a3c`; strict schemas, 24 tests, eight refusal fixtures, clean wheel smoke test | none |
| 01 | complete | `EP-001` at `30173f1`; 85 tests, SQLite replay parity, interruption and refusal matrix | none |
| 02 | complete | `EP-002` at `19bebb9`; live Core resolved both fields, returned 31 consumers over seven pages, proved at least 30 beyond configured repository scope, and verified four updates to one document URN without lifecycle mutation | none |
| 03 | complete | `EP-003` at `3ca39a1`; exact live DataHub-to-dbt mapping, two one-file applies, native validation receipt, verified rollback, idempotent retry, and contained adversarial probes | none |
| 04 | complete | `EP-004` at `25466a9`; equivalent live reconciliation, verified stable publication, one issued-plan sentinel, live late-consumer reopening, rich-graph refusal, and adversarial gate matrix | no production warehouse deletion was attempted |
| 05 | complete | `EP-005` at `ae62486`; four-decision CLI, deterministic canonical reports, exact plan confirmation, structural public redaction, keyboard/mobile browser proof, and zero axe violations | independent nontechnical operation remains phase 08 evidence |
| 06 | active | checkpoint B at `4148020` pins four official assets; C at `ef02788`/`6c9d4aa` generates deterministic quality truth; D/E at `34df09e` directly reread live Core aspects, matched 14/14 independent scenarios with zero false readiness, passed exact Git/dbt and three native fault probes, verified one publication and sentinel, and refused late/rich graphs across semantically equivalent twin runs | remove the superseded Looker release surface and rerun every post-removal acceptance command |
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
