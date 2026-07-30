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
| RC-004 | Resolve target, replacement, and consumers from live DataHub without predicted identity | `docs/PRODUCT.md` | 02 | live search, schema, identity, and ambiguity evidence |
| RC-005 | Bound every DataHub claim by scope, freshness, permissions, pagination, versions, and limitations | `docs/CONTRACTS.md` | 02 | complete and forced-incomplete evidence envelopes |
| RC-006 | Demonstrate that DataHub adds consequential context and changes a policy outcome | `docs/PRODUCT.md` | 02 | repository-only versus graph-augmented counterfactual |
| RC-007 | Publish one stable campaign summary to DataHub and verify agent-visible read-back | `docs/ARCHITECTURE.md` | 02, 04 | idempotent write, update, and digest read-back |
| RC-008 | Bind every mutable consumer one-to-one to an exact native identity | `docs/CONTRACTS.md` | 03, 06 | one-match acceptance and zero/multiple/recycled refusal |
| RC-009 | Change only an approved Git/dbt target under commit, path, fingerprint, and authorization preconditions | `docs/PRODUCT.md` | 03 | reviewable branch diff and adverse scope cases |
| RC-010 | Validate the changed repository consumer with dbt-native parse, build, tests, and declared semantic checks | `docs/PRODUCT.md` | 03 | live dbt receipt plus semantically wrong refusal |
| RC-011 | Reconcile from equivalent fresh evidence, invalidate drift, and reopen on a late consumer | `docs/ARCHITECTURE.md` | 04 | before/after snapshots and controlled reopening |
| RC-012 | Enforce the same deterministic decision in a producer-side gate that fails closed | `docs/PRODUCT.md` | 04 | live all-closed sentinel run plus live rich-graph refusal logs |
| RC-013 | Render CLI, report, DataHub summary, and gate from one canonical manifest | `docs/DECISIONS.md` | 04, 05 | matching decision and digest across every surface |
| RC-014 | Make evidence gaps, blind spots, native actions, and next steps understandable to a nontechnical operator | `docs/PRODUCT.md` | 05 | inspected CLI/report, browser, accessibility, and redaction evidence |
| RC-015 | Change and natively validate one exact live Looker saved-content consumer through the same campaign | `docs/PRODUCT.md` | 06 | live Looker receipt, compensation, and graph reconciliation |
| RC-016 | Fail closed under least privilege, tampering, concurrency, partial failure, retries, untrusted input, and recovery | `docs/RISKS.md` | 07 | threat model, fault matrix, recovery drills, and scans |
| RC-017 | Install, configure, upgrade, restore, and remove the product reproducibly from a clean environment | `docs/PRODUCT.md` | 08 | package, clean install, reference campaign, upgrade and removal evidence |
| RC-018 | Establish whether another real operator can use the workflow and obtains recurring value | `docs/PRODUCT.md` | 08 | independent run and redacted workflow observations |

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
