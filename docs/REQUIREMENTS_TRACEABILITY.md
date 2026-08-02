# Requirements traceability

This matrix prevents a broad collection of features from being mistaken for
the product. Every requirement needs direct implementation and evidence.
Passing a later phase does not silently waive an earlier requirement.

## Product requirements

| ID | Required behavior | Authority | Phase | Direct acceptance evidence |
|---|---|---|---:|---|
| RC-001 | Accept one exact legacy field, one compatible replacement, declared evidence scope, validation, and authorization | `docs/CONTRACTS.md` | 00 | [EP-000](EVIDENCE_LEDGER.md#ep-000--phase-00-foundation): strict schemas and valid plus refusal fixtures |
| RC-002 | Persist campaign events, replay state deterministically, and resume safely after interruption | `docs/ARCHITECTURE.md` | 01 | [EP-001](EVIDENCE_LEDGER.md#ep-001--phase-01-campaign-kernel): event replay, fault injection, manifest digest parity |
| RC-003 | Produce only the four deterministic final decisions from versioned policy and evidence | `docs/CONTRACTS.md` | 01 | [EP-001](EVIDENCE_LEDGER.md#ep-001--phase-01-campaign-kernel): complete transition and refusal-code coverage |
| RC-004 | Resolve target, replacement, and consumers from live DataHub without predicted identity | `docs/PRODUCT.md` | 02 | [EP-002](EVIDENCE_LEDGER.md#ep-002--phase-02-datahub-evidence-boundary): live exact dataset/field resolution and identity refusals |
| RC-005 | Bound every DataHub claim by scope, freshness, permissions, pagination, versions, and limitations | `docs/CONTRACTS.md` | 02 | [EP-002](EVIDENCE_LEDGER.md#ep-002--phase-02-datahub-evidence-boundary): 31/31 live inventory plus partial, stale, and permission cases |
| RC-006 | Demonstrate that DataHub adds consequential context and changes a policy outcome | `docs/PRODUCT.md` | 02 | [EP-002](EVIDENCE_LEDGER.md#ep-002--phase-02-datahub-evidence-boundary): one repository reference versus 31 graph consumers, conservative minimum expansion of 30, and 31 additional opaque policy blockers |
| RC-007 | Publish one stable campaign summary to DataHub and verify agent-visible read-back | `docs/ARCHITECTURE.md` | 02, 04 | [EP-002](EVIDENCE_LEDGER.md#ep-002--phase-02-datahub-evidence-boundary) and [EP-004](EVIDENCE_LEDGER.md#ep-004--phase-04-reconciliation-and-producer-gate): stable URN, exact final ready and reopened read-backs, and unchanged lifecycle |
| RC-008 | Bind every mutable consumer one-to-one to an exact native identity | `docs/CONTRACTS.md` | 03 | [EP-003](EVIDENCE_LEDGER.md#ep-003--phase-03-git-and-dbt-execution): one exact fresh DataHub URN to dbt manifest identity; all non-Git/dbt consumers remain non-mutable blockers |
| RC-009 | Change only an approved Git/dbt target under commit, path, fingerprint, and authorization preconditions | `docs/PRODUCT.md` | 03 | [EP-003](EVIDENCE_LEDGER.md#ep-003--phase-03-git-and-dbt-execution): two review branches, exact one-file diffs, approval/source binding, refusal and recovery probes |
| RC-010 | Validate the changed repository consumer with dbt-native parse, build, tests, and declared semantic checks | `docs/PRODUCT.md` | 03 | [EP-003](EVIDENCE_LEDGER.md#ep-003--phase-03-git-and-dbt-execution): live dbt receipt, verified rollback, and semantically wrong native failure |
| RC-011 | Reconcile from equivalent fresh evidence, invalidate drift, and reopen on a late consumer | `docs/ARCHITECTURE.md` | 04 | [EP-004](EVIDENCE_LEDGER.md#ep-004--phase-04-reconciliation-and-producer-gate): equivalent live scope, bounded refresh, late reopening, source-drift refusal, and disappeared-edge fixture |
| RC-012 | Enforce the same deterministic decision in a producer-side gate that fails closed | `docs/PRODUCT.md` | 04 | [EP-004](EVIDENCE_LEDGER.md#ep-004--phase-04-reconciliation-and-producer-gate): one issued-plan sentinel, replay/drift/tamper refusals, and live rich-graph refusal |
| RC-013 | Render CLI, report, DataHub summary, and gate from one canonical manifest | `docs/DECISIONS.md` | 04, 05 | [EP-004](EVIDENCE_LEDGER.md#ep-004--phase-04-reconciliation-and-producer-gate) binds reconciliation, verified publication, producer plan, and gate; [EP-005](EVIDENCE_LEDGER.md#ep-005--phase-05-operator-experience) verifies CLI/report decision and digest parity from the same manifests |
| RC-014 | Make evidence gaps, blind spots, native actions, and next steps understandable to a nontechnical operator | `docs/PRODUCT.md` | 05 | [EP-005](EVIDENCE_LEDGER.md#ep-005--phase-05-operator-experience): inspected four-decision CLI, live refusal and all-closed reports, public redaction, keyboard flows, responsive screenshots, and accessibility evidence |
| RC-015 | Retired: change and validate a live Looker consumer | `docs/DECISIONS.md` | superseded | removed from the product and completion contract by D-038; historical fixture evidence remains non-live and non-accepting |
| RC-016 | Fail closed under least privilege, tampering, concurrency, partial failure, retries, untrusted input, and recovery | `docs/RISKS.md` | 07 | [Phase 07 observations](EVIDENCE_LEDGER.md#phase-07-pre-reframe-observations): plan/apply separation, fault matrix, recovery drill, copied-store refusal, and scans pass; refresh after benchmark integration and Looker removal remains |
| RC-017 | Install, configure, upgrade, restore, and remove the product reproducibly from a clean environment | `docs/PRODUCT.md` | 08 | [Phase 08 credential-independent observations](EVIDENCE_LEDGER.md#phase-08-credential-independent-observations): reproducible package, four clean runtimes, actionable preflight, installed live Core reference, upgrade/rollback, backup, copied-state refusal, confirmed removal, and uninstall |
| RC-018 | Establish whether another real operator can use the workflow and obtains recurring value | `docs/PRODUCT.md` | 08 | [Phase 08 operator boundary](../artifacts/public/phase08/operator-boundary.json) is `NOT_RUN`; independent run and redacted frequency, friction, value, willingness, and buyer observations remain required |
| RC-019 | Prove evidence quality and zero false readiness against pinned official datasets plus an independent deterministic truth oracle | `GOAL.md` | 06 | not-run; requires the official-dataset registry, synthetic corpus, live local DataHub benchmark, native dbt receipt, refusal matrix, and inspected `EP-006` replacement evidence |

## Cross-cutting acceptance

Every requirement also inherits these conditions:

- evidence mode is explicit;
- required source failure blocks;
- no empty result proves absence;
- source-native validation is not replaced by approval;
- actual targets equal approved targets;
- source and replacement state remain valid at gate time;
- public artifacts contain no secret or sensitive source material;
- observed limitations remain visible in the final decision;
- implementation, contracts, status, evidence, risks, and decisions agree.

## Change rule

When behavior changes:

1. update the authoritative contract;
2. update the affected phase acceptance;
3. update this row without reusing an ID for a different meaning;
4. add or update tests and evidence;
5. record compatibility or reframe consequences in the decision log.

No requirement may be marked satisfied by an indirect feature count, a
presentation artifact, or baseline evidence from the preceding experiment.
