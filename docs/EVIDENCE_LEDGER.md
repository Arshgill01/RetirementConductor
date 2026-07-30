# Evidence ledger

This ledger connects product claims to inspected runtime evidence. It is not a
test-output dump. Raw or sensitive artifacts remain ignored and are referenced
only by safe digest.

## Evidence modes

| Mode | Meaning | May satisfy live acceptance |
|---|---|---|
| `live` | Observed against the named running source or native tool | yes, within recorded scope |
| `fixture` | Produced from controlled deterministic test data | no |
| `replay` | Reproduced from a prior captured artifact | no |
| `analysis` | Source-backed reasoning without a runtime claim | no |

Every entry must name its commit, command or operator action, source versions,
artifact or digest, result, limitations, and the claim it supports.

## Baseline evidence

These observations came from the preceding experiment. They justify the build
but do not complete a product phase.

| ID | Mode | Claim | Evidence reference | Status | Limitation |
|---|---|---|---|---|---|
| EB-001 | live | DataHub expanded one repository consumer to 35 graph consumers | `docs/EVIDENCE_BASELINE.md` and experiment commit `a251cb7` | accepted baseline | not executed by this product |
| EB-002 | live | graph context changed the decision from allow to refuse | `docs/EVIDENCE_BASELINE.md` and experiment commit `a251cb7` | accepted baseline | policy was experiment code |
| EB-003 | live | one dbt consumer changed and passed native tests with stale-source refusal | `docs/EVIDENCE_BASELINE.md` and experiment commit `a251cb7` | accepted baseline | no durable campaign runtime |
| EB-004 | live | a stable refusal summary was written to and read back from DataHub | `docs/EVIDENCE_BASELINE.md` and experiment commit `7ef9f58` | accepted baseline | no complete producer gate |
| EB-005 | fixture | bounded Looker lifecycle fails closed in a deterministic boundary | `docs/EVIDENCE_BASELINE.md` and experiment commit `b5233ca` | accepted baseline | not live Looker evidence |

## Product phase evidence

Replace `not-run` only after the named phase acceptance commands have run and
the produced artifacts have been inspected.

| ID | Phase | Required mode | Tested commit | Evidence | Status | Limitations |
|---|---:|---|---|---|---|---|
| EP-000 | 00 | fixture | `6692a3c` | `artifacts/public/phase00/`; executable contracts, fixtures, package, and repository checks | passed | fixture evidence cannot satisfy a live policy |
| EP-001 | 01 | fixture | not-run | state, replay, interruption, and policy evidence | not-run | none recorded |
| EP-002 | 02 | live | not-run | DataHub identity, pagination, envelope, and write/read-back | not-run | none recorded |
| EP-003 | 03 | live | not-run | Git/dbt plan, apply, validation, rollback, and receipt | not-run | none recorded |
| EP-004 | 04 | live and fixture | not-run | reconciliation, late-consumer refusal, publication, and gate | not-run | none recorded |
| EP-005 | 05 | live and fixture | not-run | canonical CLI/report parity, accessibility, and redaction | not-run | none recorded |
| EP-006 | 06 | live | not-run | Looker identity, apply, validation, compensation, and reconciliation | not-run | disposable access required |
| EP-007 | 07 | live and fixture | not-run | threat, fault, recovery, concurrency, and scan evidence | not-run | none recorded |
| EP-008 | 08 | live and operator | not-run | clean install, upgrade, reference run, and independent operation | not-run | independent operator required |

## Entry completion checklist

For each completed row, add a short section below the table with:

```text
Evidence ID:
Requirement IDs:
Repository commit:
Captured at:
Mode:
Source and tool versions:
Command or operator action:
Expected result:
Observed result:
Refusal cases:
Tracked artifact paths:
Private artifact digests:
What this proves:
What this does not prove:
Reviewer inspection:
```

An exit code without inspected output is insufficient. A tracked artifact
containing secrets or private evidence invalidates the entry until it is
removed safely and credentials are rotated where necessary.

## EP-000 — phase 00 foundation

Evidence ID: EP-000

Requirement IDs: RC-001

Repository commit: `6692a3ca20db61766bc109353fccfafb2db27b1f`

Captured at: `2026-07-30T08:52:06Z`

Mode: fixture

Source and tool versions: Python 3.13.14 in the uv environment; uv 0.11.28;
pytest 8.4.2; Retirement Conductor 0.1.0. Resolved package versions and
observed licenses are in `artifacts/public/phase00/dependencies.json`.

Command or operator action:

```text
make check
pytest
retirement-conductor validate-spec fixtures/specs/valid.yaml
retirement-conductor fixture run fixtures/specs/valid.yaml
git diff --check
```

An additional clean virtual environment installed
`dist/retirement_conductor-0.1.0-py3-none-any.whl`, ran both CLI paths, and
inspected that the generated manifest remained fixture-bounded and blocked.

Expected result: strict specification acceptance; stable generated artifacts;
source, scope, identity, evidence, and replacement refusals before mutation;
fixture evidence visibly unable to satisfy a live-evidence policy; all
repository checks passing.

Observed result: all commands exited zero; 24 tests passed; the valid fixture
generated canonical specification, envelope, event log, receipt, and manifest;
the manifest decision was `BLOCKED` with `EVIDENCE_MODE_NOT_LIVE`; eight
negative cases emitted their expected stable refusal and the tracked source
fingerprint remained unchanged.

Refusal cases: `SPEC_IDENTICAL_FIELDS`,
`SPEC_UNSUPPORTED_REPLACEMENT`, `SPEC_SCHEMA_INVALID`,
`IDENTITY_AMBIGUOUS`, `SPEC_REPLACEMENT_INCOMPATIBLE`,
`EVIDENCE_REQUIRED_SOURCE_INCOMPLETE`,
`SOURCE_FINGERPRINT_MISMATCH`, and `SCOPE_PATH_OUTSIDE_ROOT`.

Tracked artifact paths: `artifacts/public/phase00/manifest.json`,
`artifacts/public/phase00/events.json`,
`artifacts/public/phase00/receipt.json`,
`artifacts/public/phase00/refusal-matrix.json`, and
`artifacts/public/phase00/dependencies.json`.

Private artifact digests: none; phase 00 used only reviewed public fixtures.
Tracked file SHA-256 digests are respectively
`4ddfd51f212e2702f531a2e8496e2d1fb91ef21a8942620cc5601671b029b958`,
`6992b118962ceb5d596f6c9cbe6b4df2c937b17b184edc784291120095d63877`,
`485babe4c2ad8ab9baab0b8a6cbdb60c0c32b52558ea89cc38571ba30426dc03`,
`8f45d6ef3a6da41dd0686e56df897fb2b0dca2a7244c2dec759fa8791f3f2127`,
and
`2a771c77767029bc315071f5a8864b3f84bb0252a5d691390dc0a26da9168f6d`.

What this proves: the product package executes its phase 00 contracts,
normalizes the supported specification, rebuilds deterministic fixture
artifacts, and promotes the prior experiment's fingerprint and scope
invariants without importing its harness.

What this does not prove: live DataHub identity or completeness, a live
repository mutation, dbt-native validation, durable replay, readiness, or any
live integration.

Reviewer inspection: inspected normalized identity fields, the
`EVIDENCE_MODE_NOT_LIVE` blocker, receipt mode and limitation, all refusal
codes, unchanged source digest, dependency metadata, wheel contents, and
secret/public-artifact scan output.
