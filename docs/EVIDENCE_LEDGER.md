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
| EP-001 | 01 | fixture | `30173f1` | `artifacts/public/phase01/`; state, replay, interruption, policy, and integrity evidence | passed | no external or native integration exercised |
| EP-002 | 02 | live | `19bebb9` | `artifacts/public/phase02/`; DataHub identity, pagination, envelope, scope comparison, and stable write/read-back | passed | synthetic disposable Core graph; no authenticated or Cloud boundary |
| EP-003 | 03 | live | `3ca39a1` | `artifacts/public/phase03/`; Git/dbt identity, exact apply, rollback/reapply, native receipt, and adversarial containment | passed | local disposable Git repository and DuckDB; no production source |
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

## EP-001 — phase 01 campaign kernel

Evidence ID: EP-001

Requirement IDs: RC-002, RC-003

Repository commit: `30173f160c3c87a8daf0a3c1988c7ccde10662ec`

Captured at: `2026-07-30T09:15:57Z`

Mode: fixture

Source and tool versions: Python 3.13.14; SQLite 3.46.1; uv 0.11.28; pytest
8.4.2; Retirement Conductor 0.1.0.

Command or operator action:

```text
make check
pytest tests/unit tests/contracts tests/integration/test_campaign_store.py
retirement-conductor campaign replay fixtures/campaigns/blocked
retirement-conductor campaign evaluate fixtures/campaigns/blocked
git diff --check
```

A clean wheel environment also replayed the fixture, created a SQLite
campaign, closed it, reopened it, and inspected the same campaign through the
installed CLI.

Expected result: every declared transition and four policy outcomes behave
deterministically; malformed evidence never promotes; committed events replay
without duplicates after each injected boundary; corrupt chains, caches,
clocks, receipts, approvals, input digests, locks, and overlapping native
claims refuse.

Observed result: `make check` passed all 85 tests and package checks; the
mandated focused command passed 73 tests; the three-event blocked fixture
replayed twice to manifest digest
`sha256:5466473b6fe03d35c2a9d3b5f6e86301245ecb3dcdf8e804fa1f58d1fbaf70ce`;
the separate evaluate command returned the same digest and `BLOCKED` decision.
Interruption tests resumed before insert, after insert rollback, and after
commit without a duplicate event or false readiness.

Refusal cases: illegal campaign and consumer transitions; fixture and replay
receipts under live policy; missing, expired, wrong-campaign, wrong-plan,
wrong-source, and wrong-scope approvals; forbidden, invalid, and expired
waivers; late consumers; overlap; idempotency-key conflict; event sequence,
chain, receipt, and materialized-cache corruption; clock rollback, future
evidence, invalid timestamps, expiration boundary, and excessive skew;
policy, validator, and authorization input drift; single-writer mismatch and
local lock contention.

Tracked artifact paths:
`src/retirement_conductor/migrations/001_initial.sql`,
`fixtures/campaigns/blocked/events.json`,
`artifacts/public/phase01/blocked-manifest.json`,
`artifacts/public/phase01/kernel-evidence.json`, and
`artifacts/public/phase01/refusal-coverage.json`.

Private artifact digests: none. The tracked file SHA-256 digests are
`752ea43795f3b6005a9b1136809beac445b47488b186aad39bdb8e444cf20bf1`,
`b75afdc64efc15d2fcf3d168b81bc88025d398dd99165c604f27daa714db7729`,
`faa7e3f51349b696d943d2a4146e83ea71199043f58b1e4e3d023194eeb3cf85`,
`b4c956d40d85a377d87ca1df1258c314034554a2be70dd52b7301f5c82c49d12`,
and
`64daa846758ffe1c24c30b25b4053c64e4f1aa485dc6a75dd170f19869998c12`,
respectively.

What this proves: one campaign has a versioned append-only SQLite event
stream, legal state machines, idempotent recovery, exact approval and receipt
binding, injected trusted-time checks, deterministic four-way policy, and a
canonical replayed manifest whose cache is subordinate to event replay.

What this does not prove: live DataHub evidence, live source mutation or
validation, distributed coordination, a live trusted-time provider, or gate
enforcement.

Reviewer inspection: inspected the SQL migration, all three raw events and
their predecessor digests, replayed state and blocker codes, canonical
manifest parity, refusal registry report, interruption assertions, corrupted
database cases, and packaged migration/schema contents.

## EP-002 — phase 02 DataHub evidence boundary

Evidence ID: EP-002

Requirement IDs: RC-004, RC-005, RC-006, RC-007

Repository commit: `19bebb9d54f22dcbb7f6e3fc922f8213eb719d53`

Captured at: `2026-07-30T10:10:31Z`

Mode: live

Source and tool versions: DataHub Core GMS and upgrade images v1.6.0;
DataHub CLI and SDK 1.6.0; DataHub Core source
`b5c566f3e215c3074dbd1443101a916714dd88b3`; self-hosted DataHub MCP
server 0.6.0 at
`9a6946daa7d30eb481c82dd8ee5e15ae6526a3c9`; Python 3.11.15; uv 0.11.28;
Retirement Conductor 0.1.0. The exact component matrix is retained in
`artifacts/public/phase02/capability-evidence.json`.

Command or operator action:

```text
make datahub-core-up
make datahub-seed
retirement-conductor datahub preflight
retirement-conductor campaign inventory --campaign ret-orders-live-status
retirement-conductor campaign publish --campaign ret-orders-live-status
retirement-conductor campaign verify-publication --campaign ret-orders-live-status
make phase02-evidence
make check
git diff --check
```

The publish and verification commands were repeated after fresh inventory to
exercise stable updates rather than only document creation.

Expected result: exact live target and replacement resolution; complete
bounded pagination; visible freshness, permissions, versions, limitations,
and raw artifact links; a material graph-scope expansion; one stable summary
that reads back exactly; and no target lifecycle mutation. Partial, stale,
permission-denied, missing, ambiguous, or mismatched evidence must refuse or
remain non-ready.

Observed result: the live Core graph resolved the Snowflake `orders` dataset
and the exact `legacy_status` and `order_status` fields. Seven GraphQL pages
returned all 31 advertised downstream consumers with no page error. A bounded
read-only scan found one configured repository field-reference consumer; even
assuming that consumer overlaps one graph entity, DataHub contributed at
least 30 additional consumers and added 31 visible
`POLICY_CONSUMER_OPAQUE` blockers. The campaign remained `UNSAFE`.

The MCP `save_document` surface was exercised four times against the same
logical key and returned one stable document URN. GraphQL `document` read-back
matched the exact published content, `searchDocuments` returned one exact
title/URN match, and the target deprecation value remained null before and
after every write. SQLite remained authoritative for the 12-event campaign
stream.

Refusal cases: controlled pagination failure produced a `PARTIAL` required
source; stale source time produced `STALE`; zero-match, quoted/case,
platform-instance, duplicate-display, missing-field, and duplicate-field
cases could not authorize a guessed identity; a simulated HTTP 403 produced
`SOURCE_DATAHUB_PERMISSION_DENIED`; mismatched document content, changed
document identity, or changed lifecycle produced
`EVIDENCE_PUBLICATION_MISMATCH`. Query-history absence remained zero
observations with no closure authority, ownership remained routing-only, and
table-only lineage left consumers opaque. These adverse cases are controlled
tests over the same adapter code; the positive inventory and write/read-back
are live.

Tracked artifact paths:
`artifacts/public/phase02/capability-evidence.json`,
`artifacts/public/phase02/inventory-evidence.json`,
`artifacts/public/phase02/publication-evidence.json`, and
`artifacts/public/phase02/phase02-evidence.json`.

Private artifact digests: the ignored live capability fingerprint is
`sha256:38618c3adb547dbf074983d47ed1f83aaf13ba0d527a7e24b88315db26f36540`;
the normalized snapshot is
`sha256:b1bebace52ff9935711100a90520cb223e911aa36db9f522af2d1774f8f766e5`;
the evidence envelope is
`sha256:e0645a3147101600a37aa6cccebc95f714ad0b85140424fc7ce471ae8da507ad`;
the latest exact read-back artifact is
`sha256:02e9026a20750a6264ccf638ea970b60a5c62214df839b8435618e93320e1497`;
and both lifecycle observations digest to
`sha256:55fe2a34f16452e099fb2698de63d8b45418deea23dec8e98ccc38778f2593f3`.
The 15 redacted raw observation digests and safe runtime names are indexed in
the tracked inventory evidence.

The tracked artifact file SHA-256 digests are, respectively,
`1bea1d2e5269f9840f2814da82008c6021ad284d01bf82863b66c9598cb733c3`,
`8162c91a111760f84a85a98dcd0d542bdb08f16dc24423377c9bbc0cc10ef835`,
`98bf8a83ac2593cae3397a9dabaecdaed3e939be96cab7bfd0cbd621ee117f54`,
and
`5058bb9b0e36c6c81e4d6f4823a0e58c516df3e6a5cddc811a482774709cc7f5`.

What this proves: the product, rather than the preceding experiment, can
resolve one exact field pair from a running DataHub Core instance, capture a
fully paged evidence-bounded inventory, conservatively demonstrate
consequential catalog scope, preserve evidence granularity, retain campaign
authority locally, and update and independently verify one durable DataHub
summary without touching lifecycle state.

What this does not prove: production or authenticated DataHub permissions,
DataHub Cloud parity, a real ingestion connector's retention behavior,
repository-native identity, dbt mutation or validation, reconciliation,
readiness, producer-gate enforcement, or universal consumer completeness.
Core v1.6.0 did not expose `isPartial`; that absence remains an explicit
limitation. Query history exposed no retention window and cannot close a
consumer.

Reviewer inspection: inspected the capability fingerprint, all seven raw
lineage page digests, exact schema resolution, normalized claims, field- versus
table-level limitations, source update time, one-versus-31 scope comparison,
envelope and snapshot digests, publication event receipts, exact document
content, unique document search result, and null lifecycle before and after.

## EP-003 — phase 03 Git and dbt execution

Evidence ID: EP-003

Requirement IDs: RC-008, RC-009, RC-010

Repository commit: `3ca39a111f8ad2e035152931960c314d832a0118`

Captured at: `2026-07-30T10:57:13Z`

Mode: live

Source and tool versions: the phase 02 DataHub Core v1.6.0 and self-hosted MCP
0.6.0 boundary; Git 2.53.0; dbt-core 1.12.0; dbt-duckdb 1.10.1; DuckDB 1.5.5;
bubblewrap 0.11.1; Python 3.11.15; uv 0.11.28; Retirement Conductor Git/dbt
adapter 0.1.0.

Command or operator action:

```text
make git-dbt-tool
make git-dbt-workspace
make datahub-seed
retirement-conductor campaign create fixtures/specs/git-dbt-live.yaml ...
retirement-conductor adapter git-dbt preflight --campaign ret-orders-git-dbt
retirement-conductor adapter git-dbt plan --campaign ret-orders-git-dbt
retirement-conductor adapter git-dbt apply --campaign ret-orders-git-dbt
retirement-conductor adapter git-dbt authorize --campaign ret-orders-git-dbt ...
retirement-conductor adapter git-dbt apply --campaign ret-orders-git-dbt
retirement-conductor adapter git-dbt compensate --campaign ret-orders-git-dbt
retirement-conductor adapter git-dbt plan --campaign ret-orders-git-dbt
retirement-conductor adapter git-dbt authorize --campaign ret-orders-git-dbt ...
retirement-conductor adapter git-dbt apply --campaign ret-orders-git-dbt
retirement-conductor adapter git-dbt validate --campaign ret-orders-git-dbt
retirement-conductor campaign evaluate --campaign ret-orders-git-dbt
make phase03-evidence
make check
git diff --check
```

The first apply command intentionally preceded authorization and exited 2.
The authorized apply was then repeated before compensation, and the evidence
generator separately repeated a native apply while counting Git commits.

Expected result: one fresh DataHub consumer maps to one exact dbt manifest
identity; repository evidence joins the coverage envelope; planning does not
write; approval binds campaign, plan, source commit, path, and capability;
only one allowlisted file changes on a review branch; dbt parse, seed, build,
and test pass; rollback restores and validates the original; reapply produces
one new change and one accepted live receipt; hostile or stale inputs cannot
expand scope or escape the validator; readiness remains refused until fresh
reconciliation closes the other consumers.

Observed result: fresh DataHub evidence returned 31/31 consumers over four
configured ten-item pages. Exact manifest metadata mapped
`orders_model_00.sql` to one matching DataHub URN, while the repository source
recorded main-only coverage and its blind spots. Both plans pinned source
commit `a827ddfe4543b4f767e3628f131ee739ef681605` and the same before/after file
fingerprints. Applies `fb4ba869579b603817f46354aa1e66a0ca918631` and
`123e6908c229e0e207ee29968f31a5ee2e859736` each changed only
`models/orders_model_00.sql`.

The first apply replay retained one commit and the same apply digest. Git
compensation commit `f7a2a0f3c9142282cea0d4cad630dea1e9e0e69f` restored the
original fingerprint and passed native verification before the second plan.
Final native parse, seed, build, and test each exited zero in a copied,
allowlisted-environment bubblewrap workspace with no host home, source
repository, or network namespace mounted. Receipt
`sha256:b89b6010882e93c0cffeb01e893598e2e71fe223c8379d0c2b11e65e04ac6bab`
closed exactly consumer `dh-39b6c65bcbecb310e0cd` as `VALIDATED` and retained
the replacement identity plus matching DataHub/dbt `VARCHAR` evidence.

The phase ended honestly `UNSAFE` and `BLOCKED`: 30 other graph consumers
remain `OPAQUE`, and `RECONCILIATION_REQUIRED` remains present. Phase 03 did
not convert successful native execution into a readiness claim.

Refusal cases: missing approval (`AUTH_APPROVAL_MISSING`); disabled apply
capability (`AUTH_APPLY_DISABLED`); dirty content (`SOURCE_GIT_DIRTY`); moved
commit (`SOURCE_GIT_BRANCH_MOVED`); unauthorized or expanded targets
(`SCOPE_TARGET_NOT_ALLOWED`); traversal (`SCOPE_PATH_OUTSIDE_ROOT`); symlink
and external dependency (`VALIDATION_SCOPE_VIOLATION`); missing or
incompatible replacement (`SPEC_REPLACEMENT_INCOMPATIBLE`); and intervening
post-apply content (`COMPENSATION_CONFLICT`). The semantic-wrong model failed
dbt build. Host-secret, subprocess, and network attempts failed inside the
isolated validator; no host secret or marker appeared. A malicious Git
post-commit hook was bypassed through the forced empty hooks path.

Tracked artifact paths:
`artifacts/public/phase03/execution-evidence.json`,
`artifacts/public/phase03/adversarial-evidence.json`, and
`artifacts/public/phase03/phase03-evidence.json`.

Private artifact digests: repository preflight
`sha256:615dcaf807e55d8b01d6f5ecb8e4db0b4153591864a6f41e899ae1282c80a3e3`;
cross-source binding
`sha256:8aa01e711b8ac43e996ce6f65454058158528507a8625b1014bfd39ac473f57c`;
current plan
`sha256:71a562a448f1cc76084d1d91e57106e198f06e5db9a5ac68dcc95e9e6e04dc1e`;
current apply
`sha256:557739197e41b3de7fd4de48343461ec1a2cd40150369166b9597bbfffe9a9f9`;
compensation
`sha256:23f6ee228141ff0feeb346546799bffbd2cd3f38a767e3b6092e3d4d568aefce`;
final validation
`sha256:f0eac4ea3c19c2af6747005fae4dd0f15a0b7678ef62c98fa7b8422779d88f93`;
and event stream
`sha256:df3ad815795d62da59b5f2babafc8f6c9b0c1002c7bee12a3a20e79c14562eea`.
The ignored adversarial probe root is referenced only by safe identity
`sha256:d34235f5262b10486e4b68cf5219c5a62f0ba0eb73ef091d764c4873b7e70ff8`.

The tracked artifact file SHA-256 digests are
`050f9829647bd78e96bba5775e7e7189b75abe79e60a83842bc59cb7abb8c9a4`,
`49880a017904daa4106925489450bea9cc0fd1c679e5b8153e05d4afcf859f55`,
and
`200d54664d571b94b67dbfb0b17f574b90b82ffbc8c7bd35efa772ea3cf0cfc4`,
respectively.

What this proves: the product owns a real Git/dbt operational slice from
fresh cross-source identity through bounded authorization, mutation, native
validation, recovery, retry, receipt acceptance, and safe refusal. The
campaign engine, not the adapter, still owns the non-ready decision.

What this does not prove: production repository or warehouse behavior,
non-default branch completeness, arbitrary dbt project safety, every kernel
or container boundary, an interrupted mutation whose response is lost,
reconciliation, producer-gate enforcement, Looker execution, or universal
field-retirement safety.

Reviewer inspection: inspected both plan and apply bindings, one-file Git
diffs, branch heads, restored fingerprint, all native command exit codes,
sandbox mounts and limits, exact receipt consumer/URN and compatibility
evidence, campaign event digest, remaining blockers, every adverse refusal,
failed semantic build, and absence of secret, hook, subprocess, and network
escape markers.
