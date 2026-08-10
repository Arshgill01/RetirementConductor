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
| EP-004 | 04 | live and fixture | `25466a9` | `artifacts/public/phase04/`; equivalent reconciliation, late reopening, verified publication, one-time gate, and refusal matrix | passed | disposable Core, Git, DuckDB, and harmless sentinel; no warehouse deletion |
| EP-005 | 05 | live and fixture | `ae62486` | `artifacts/public/phase05/`; four-decision CLI, deterministic canonical reports, exact apply confirmation, structural redaction, browser, keyboard, and accessibility proof | passed | live view reuses the disposable phase 04 manifest; independent human comprehension remains phase 08 |
| EP-006 | 06 | live local and fixture | `8f5eb58` | `artifacts/public/phase06/`; pinned official inputs, deterministic corpus and oracle, direct DataHub readback, exact Git/dbt receipt, refusal matrix, one producer sentinel, and zero false readiness | passed | fixture inputs do not prove production coverage; readiness is bounded by one DataHub and Git/dbt envelope |
| EP-007 | 07 | live local and fixture | `6e4ca87` | `artifacts/public/phase07/`; post-removal least-privilege, fault, recovery, concurrency, dependency, secret, public-artifact, and benchmark-binding evidence | passed | deterministic local fault injection does not prove production host, secret-provider, or distributed-storage controls |
| EP-008 | 08 | live local, fixture, and analysis | `c3440b2` | `artifacts/public/phase08/`; post-removal reproducible package, four clean installs, preflight, live installed-wheel Core reference, upgrade/rollback, removal, compatibility, and explicit operator boundary | engineering passed | RC-018 remains follow-on `NOT_RUN`; no independent-operation or customer-value claim |

### Phase 06 checkpoint B — pinned official inputs

Tested behavior commit: `4148020`

Modes: live public-source acquisition plus deterministic local verification and
fixture refusal tests. This is not live campaign or customer evidence.

Observed source: `datahub-project/static-assets` commit
`a6479c691dd2a40dd89563396d9c8b2b28bee83c`, selected from the official
DataHub hackathon resources page. The registry pins the fiction-retail,
healthcare, nyc-taxi clean, and nyc-taxi stale SQLite assets with their
documented CC0 or NYC public-domain license evidence.

Commands:

```text
make phase06-data
make check
unzip -l dist/retirement_conductor-0.2.0-py3-none-any.whl
tar -tzf dist/retirement_conductor-0.2.0.tar.gz
```

Observed result: acquisition downloaded four pinned assets totaling
312,086,528 bytes into the ignored content-addressed cache. Every byte size,
SHA-256, pinned URL, reviewed license, and SQLite header matched the registry.
The immediate network-free verification matched all four entries. The
registry digest is
`sha256:b0a4c716c932df7967453ce66a59863b7dc6e79ad39b46fff69464774176c6e4`;
the acquire and offline receipt digests are
`sha256:516b01344e792c6e8fdca2a8dace629ea38fd87f01d12e9c91b00fc954635081`
and
`sha256:0a2b09c521d273dc8f98724f098f12140246c0f8034ba26353c67d1e5f987488`.
The package inspection found the registry and both schemas in the wheel and
source archive, but no database bytes.

Failure evidence: fixture tests refuse a moving source URL, an unreviewed
license, a missing offline entry, wrong size, wrong checksum, and an
unexpected ZIP member. Cache receipts expose only logical content keys, not
host paths or source rows.

Validation result: 236 tests, Ruff, formatting, strict mypy, 168 required-file
and 144-link validation, a 299-file secret scan, the 53-file historical
public-artifact review, source and wheel builds, and `git diff --check` passed.

Reviewer inspection: inspected both real receipts, the exact registry, all
four upstream README license statements, the package member lists, and the
refusal assertions. The large databases remain ignored.

Limitations: no corpus was generated, no source table was queried for the
benchmark, no DataHub ingestion or direct reread occurred, no campaign ran,
and no public Phase 06 artifact was promoted. `EP-006` therefore remains
active and not passed.

### Phase 06 checkpoint C — deterministic corpus and oracle

Tested behavior commits: `ef02788` with the four-component dataset-identity
correction and regenerated receipts at `6c9d4aa`

Modes: deterministic generated fixture data plus read-only probes against the
four pinned official SQLite assets. This is not production or customer data.

Commands:

```text
make phase06-data
make check
jq <aggregate projections only> \
  .retirement-conductor/benchmark/generation-a/quality-report.json
jq <row-id-free projection> \
  .retirement-conductor/benchmark/generation-a/fault-manifest.json
unzip -l dist/retirement_conductor-0.2.0-py3-none-any.whl
```

Observed result: seed `20260802`, scale `medium` selected 2,500 orders and
closed them over 2,355 customers, 5,765 order items, 3,400 products, 499
suppliers, 7,826 inventory rows, 15 warehouses, 1,983 shipments, 203 returns,
and 151 promotions. All primary keys, 11 foreign-key relationships, temporal
constraints, nonnegative order totals, replacement null checks, and
`legacy_status = order_status` semantic-control checks had zero violations.
All nine source status categories remained represented.

The exact private fault manifest planted 25 rows each (1%) for replacement
null inflation, valid-category semantic drift, and unmapped values. Aggregate
inspection did not expose the row IDs. The independent oracle contains 14
scenarios: one isolated readiness case and 13 blocked or unsafe cases covering
rich/late consumers, partial pagination, stale native data, table-only
lineage, ambiguous identity, type and value incompatibility, null and semantic
drift, healthcare selective impact, metadata-only closure, and disappearing
edges. Its module does not import campaign policy, and mutation tests show the
expected result changes when truth facts change.

Two complete generations had identical content and receipt bytes across all
16 artifacts. Their common generation receipt digest is
`sha256:bcda2b5a4ed0b4f133b0b130ca0ffad1ef8735685e2f9521e84dcb94b811b83a`;
the oracle, quality report, and private fault manifest digests are
`sha256:aa07af1bf4d416a7729ce0a39a8fccee9766cd23153b844b09b000b7a71c25f5`,
`sha256:14fda1e5e15d93530f96e82145297d97c496378ad27ebd769933efa7610c4fda`,
and
`sha256:fda8e19b29441cb6685f4c420926eda02e299f66d39535c70ed6adb132b04229`.

Official read-only probes observed `PRAGMA quick_check=ok` for every asset.
Fiction-retail had the documented 150,000 orders and zero observed foreign-key
orphans. Healthcare had 1,215 negative billing rows, 555 null-name rows, 832
invalid-age rows, and 277 date swaps; branch schemas isolate age from billing
and billing amount from demographics, while null names physically propagate
to both branches. The pinned nyc-taxi stale database has a native gap from
2016-03-01 to 2016-03-10 (nine days) and zero zero-trip mart rows. This differs
from its README's three-day and empty-load description, so observed bytes—not
the prose—control benchmark expectations.

Validation result: 242 tests, Ruff, formatting, strict mypy, 182 required-file
and 144-link validation, a 317-file secret scan, the 53-file historical
public-artifact review, source and wheel builds, and `git diff --check` passed.
Wheel inspection found generator/oracle code, registry, and schemas but no
database or CSV row files.

Limitations: the controlled graph has not yet been ingested or read back from
DataHub, oracle results have not yet been compared with the campaign engine,
native dbt has not run on this corpus, and no Phase 06 public evidence has been
promoted. `EP-006` remains active.

### Phase 06 checkpoints D/E — live evidence-quality campaign

Tested behavior commit: `34df09e`

Modes: live local DataHub Core, MCP, Git, and dbt over pinned official and
deterministically generated fixture data. This is integration evidence, not
production or customer coverage.

Commands:

```text
make phase06-benchmark
make phase06-benchmark
make phase06-evidence
make phase06-evidence
make check
uv run python scripts/check_secrets.py
uv run python scripts/check_public_artifacts.py
git diff --check
```

Observed result: DataHub Core image `acryldata/datahub-gms:v1.6.0` was healthy
on loopback and the pinned MCP source commit
`9a6946daa7d30eb481c82dd8ee5e15ae6526a3c9` was clean. Direct GMS aspect
reread recovered the exact six-field schema, `legacy_status ->
normalized_status` field lineage, owner, domain, tag, glossary term, and one
successful quality assertion bound to quality digest
`sha256:14fda1e5e15d93530f96e82145297d97c496378ad27ebd769933efa7610c4fda`.
The direct-readback digest is
`sha256:f7523d432743b0d94fbeccd1469596ca07d9c8e0666434201b354bc81db847cf`.

The controlled isolated graph recalled its one expected dbt consumer exactly.
An injected first-page failure produced `PARTIAL` with
`EVIDENCE_PAGINATION_FAILED`; replacement `TEXT` to `INTEGER` drift refused
as `SPEC_REPLACEMENT_INCOMPATIBLE`. The independent oracle matched all 14
scenario decisions and refusal-code sets through the real policy boundary,
reported zero false readiness, and rejected an intentionally corrupted
expectation.

The approved apply changed exactly
`models/orders_status_summary.sql`. dbt 1.12.0 parse, seed, build, and test all
passed on the clean corpus. Native fault probes then observed null inflation
fail `not_null` and source parity, semantic drift fail source parity, and an
unmapped category fail accepted values and source parity. Their receipt digest
is `sha256:274523635074ec210ab8a22f24f849f153c055ec2a2ee3ca7547c88f29948bd7`.

The reconciled isolated campaign reached `READY_TO_RETIRE`, one DataHub
document write was agent-read-back verified without lifecycle mutation, and
one producer plan wrote exactly one harmless sentinel. A late Spark consumer
changed the same campaign to `UNSAFE` with `POLICY_CONSUMER_OPAQUE` and
`RECONCILIATION_NEW_CONSUMER`; the gate refused and the sentinel count stayed
one. The separate rich graph retained both dbt and table-only Tableau entities
as opaque and `UNSAFE`.

Two complete live runs had different honest time-bound evidence digests but
the same time-independent semantic digest
`sha256:c60c2a91bc5202f794357052833598e1bd824200ffe047f2b51d1b77f6d3ed54`.
Two public promotions were byte-identical. Phase evidence digest is
`sha256:f1b5965eb5f70d20d9e5410f3673a23c9ebd781bef3145163da3d2271117c285`;
its tracked file SHA-256 is
`cc0baa002668cab4d956181b39b15b26767f65308ddab98ff13d62977acc8c9d`.

Validation result: 242 tests, Ruff, formatting, strict mypy, 187 required-file
and 144-link validation, a 322-file secret scan, the 56-file public-artifact
review, source and wheel builds, and `git diff --check` passed. Public review
found no raw source rows, exact planted row IDs, credentials, cache paths,
private host paths, or raw native output.

Reviewer inspection: inspected both live summaries and semantic digests; all
14 expected/observed comparisons; direct schema, lineage, context, and quality
aspects; clean and failing dbt receipts; exact apply targets; ready, late, and
rich manifests; publication read-back; gate ledger and sentinel count; all
eight public artifacts and their digests; package build output; public and
secret scans; and staged whitespace.

Limitations: fixture data does not prove production coverage; readiness is
bounded by one DataHub and Git/dbt evidence envelope; opaque consumers are not
auto-mutated; and the producer action is a harmless sentinel.

### Phase 06 post-removal confirmation

Tested behavior commit: `8f5eb58dc5f8c05149a819a92907ff0c8ce96901`

Commands:

```text
make check
make phase06-benchmark
make phase06-evidence
uv run python scripts/check_public_artifacts.py
uv run python scripts/check_secrets.py
git diff --check
```

Observed result: the supported CLI, deployment profiles, runtime modules,
schemas, recipes, fixtures, and active tests contain only DataHub and Git/dbt
product boundaries. The full post-removal live-local campaign again matched
all 14 oracle scenarios with zero false readiness. Its raw evidence digest is
`sha256:d4f563f64cd71bde350c6968570c75d576016268c43d4eda4c98e5457447c0f7`.
The time-independent semantic digest remained
`sha256:c60c2a91bc5202f794357052833598e1bd824200ffe047f2b51d1b77f6d3ed54`
and matched two earlier full runs.

The exact Git/dbt target, clean dbt commands, three expected native fault
failures, DataHub direct-readback digest, ready/late/rich decisions,
publication read-back, and one-sentinel gate behavior were unchanged. The
regenerated Phase 06 evidence digest is
`sha256:b930045d5769c9b7d938f5079dd4a37e4621b23796a0fdf45ad2ddd34e20e4b9`;
the tracked summary file SHA-256 is
`73701eaf920b0da5b9388a9372c4118a70ba7bdd1f82dcc7b19b101538c059de`.

Validation result: 182 tests, Ruff, formatting, strict mypy, 174 required-file
and 144-link validation, a 302-file secret scan, the 56-file public-artifact
review, source and wheel builds, and `git diff --check` passed. Inspection of
the current 0.2.0 source archive and wheel found no deprecated adapter or
modeling-language member. `EP-006` is complete.

### Historical Phase 06 Looker observations — superseded

These observations truthfully record the former credential-independent Looker
work and one read-only external boundary check. D-038 removed that path from
the product and completion contract. They do not satisfy or contribute to the
replacement `EP-006` benchmark row.

Repository commits:

- `00db298a77f0c0926a5bd4e6fb0a6dd77076ac41` — bounded API 4.0 adapter,
  immutable identity, plan/apply/validate/compensate, and refusal contracts;
- `34351775974995266de4bcf8e727b8f5e9963f06` — durable campaign lifecycle,
  intent recovery, inventory extension, and receipt handling;
- `5454594fb1e35f08ff3c008e337968d2e832a4ae` — scoped DataHub recipes,
  official configuration validation, LookML fixture, and no-secret packet;
- `a57b06e70fba52d7644883f0278201c2bf4e1b69` — fresh native plus
  legacy/replacement graph reconciliation and selective receipt invalidation;
- `e6183d1d07936c6ce348b5fab50a770435faa574` — exact compensation-to-apply
  binding across replan and reapply;
- `9380815c3f29497cecb3f593b5c3dda18f337be4` — corrected exact LookML
  connection mapping, official local ingestion, and direct entity reread;
- `e128e206d079729abec2858ce28f4ec446992e7b` — deterministic phase 06
  lifecycle, recovery, refusal, reconciliation, and claim-boundary artifacts.
- `813bf209cb5760b9963e195f57189152ad46cc41` — campaign-safe no-secret
  handoff whose resume command does not assume unavailable campaign state;
- `eb7206708c145e4d8a50200fb6105a60207cb515` — regenerated handoff evidence
  binding deployment preflight and the exact campaign-bootstrap prerequisite.

Captured through: `2026-07-30T15:22:08Z`

Modes:

- fixture for native API and campaign behavior;
- live local DataHub Core with fixture LookML input for the parsing and
  field-lineage observation, explicitly not live Looker evidence;
- analysis for the access contract;
- live read-only GCP control-plane observation for zero-cost pretrial state,
  explicitly not live Looker adapter evidence.

Commands or operator actions:

```text
make phase06-recipes
datahub ingest run -c deploy/datahub/recipes/looker-lookml.yml
python scripts/inspect_phase06_lookml_ingestion.py --report <ignored-report>
make phase06-evidence
retirement-conductor adapter looker access-packet --campaign ret-orders-looker-live
make check
CLOUDSDK_CONFIG=<dedicated-looker-config> \
  .retirement-conductor/looker-access/verify_zero_cost.sh
```

Observed result: the pinned official DataHub 1.6.0 configuration models
accepted both recipes. The first real parser run exposed that environment
references are not expanded in mapping keys and dropped the model; the fixed
recipe binds the fixture's exact `retirement_fixture` connection and includes
its manifest. The corrected run emitted 20 source events, discovered one
model and one view, dropped neither, and reported no source or sink warning or
failure. Direct GMS reread then found the exact LookML dataset with fields
`id`, `legacy_status`, and `order_status`, one upstream table, and three
matching field-level lineage edges.

DataHub's 1.6.0 report also set `event_not_produced_warn=true`, logged a
contradictory no-metadata message, and reported zero sink records even though
the aspects were stored. The tracked evidence therefore records those
counters as a connector limitation and treats the direct aspect reread as
authority. The raw ignored report digest is
`sha256:e2fffb6cbc559ccdc60340b657287a04f8a410a9a54cf6428fd3af0345133a25`.

The generated deterministic bundle covers exact one-Look planning, schedules
and expanded scope, invalid replacement, native Content Validation and
bounded query comparison, compensation, replan and reapply, stale
compensation rejection, fixture receipt rejection, missing permissions,
recreated identity, intervening edit, dropped response, hard interruption,
table-only lineage, persisting legacy edge, combined Git/dbt plus Looker
reconciliation, and selective stale receipt handling. It reproduced
byte-for-byte on a second run. Its rollup states
`NOT_SATISFIED_LIVE_BOUNDARY`, has canonical digest
`sha256:e1a9e9e3cf035dbd541fb71ed4e16940fff352093a0c3b0577aec8c42bafaed7`,
and keeps `EP-006` `not-run`.

The no-secret access packet reported every unresolved variable by name, kept
apply disabled, listed adapter and ingestion permissions as unverified,
contained no supplied value, and had deterministic fixture digest
`sha256:80b67e096a1f4d5bf01b6ce62c83bc5309f9e622676151c97ec4617408f84a74`.
Its exact resume command is secret-safe `looker-plan` deployment preflight,
and it states that adapter preflight requires an exact campaign created only
after live ingestion resolves the native target, DataHub URN, and graph
digest. The latest `make check` passed 228 tests, Ruff, formatting, strict
mypy, 164-file repository validation, a 294-file secret scan, a 53-file
public-artifact review, source and wheel builds, and `git diff --check`.

The dedicated read-only pretrial script observed zero Looker instances,
unallocated trial and paid Looker quota, BigQuery daily query quota zero, and
stored bytes zero, with `PROVISIONING_ALLOWED=false`. No instance, IAM role,
table, query, quota, or paid resource was created or changed.

What this proves: all currently exercised deterministic boundaries fail
closed; the second adapter participates in the same campaign, receipt, and
reconciliation semantics; official DataHub 1.6.0 both accepts the recipe
configuration and parses the public LookML fixture into exact stored field
lineage; contradictory connector reporting is detected by direct reread; and
the missing live boundary can be requested without disclosing a secret.

What this does not prove: Looker authentication or effective permissions; a
live DataHub-to-Looker identity; a live saved-Look mutation, Content
Validation run, query execution, compensation, delete/recreate, lost response,
saved-Look connector ingestion, graph refresh, accepted live receipt, combined
live campaign, or `EP-006` acceptance. The local LookML parse and zero-cost
GCP observation are not substitutes for any of those.

Tracked artifact paths:
`artifacts/public/phase06/lookml-ingestion-evidence.json`,
`artifacts/public/phase06/adapter-evidence.json`,
`artifacts/public/phase06/recovery-evidence.json`,
`artifacts/public/phase06/reconciliation-evidence.json`, and
`artifacts/public/phase06/phase06-preacceptance-evidence.json`.
Their file SHA-256 digests are
`6fa061e1c3afeda47ba0bbb4fd493322479f7d5125cf3b403dfad9ab9ba33ba1`,
`e396d28441cdaf6cd2053b8c660a041c6aae4f99489bae177d07fd08b0933890`,
`83e9c04287463f35ff32d2031c8f4bac83b34a3e5d1a6313b4181ad443ee8d94`,
`01ace2fb4ec80495aa97766a1a4b806ef93f970041e9bdbad95ca4e7f8010aec`,
and
`f2a3166cc4398154d33375ec4b3812fda98970290194a0e65e3f21db59d4556b`,
respectively.

Reviewer inspection: inspected the local ingestion report and stored schema
and lineage aspects; the plan and receipt schemas; redacted
snapshots; actual target and changed-field assertions; intent state
transitions and PATCH counts; compensation conflict; recreated identity
digests; old-compensation rejection after replan; graph edge states; combined
evidence-source set and selective invalidation; generated access packet;
campaign-safe deployment preflight and campaign-bootstrap prerequisite;
recipe model output; deterministic artifact twins; full test output; secret
and public scans; and zero-cost pretrial result.

### Phase 07 pre-reframe observations

These observations cover the credential-independent Phase 07 checks at their
recorded commit. They require refresh after the benchmark is integrated and
the deprecated Looker release surface is removed.

Evidence ID: EP-007 (credential-independent portion)

Requirement IDs: RC-016

Repository behavior commit:
`4fc5b2d2b08e98b57a3cc1292fb85008549b2179`

Tracked evidence commit:
`6feb1bc890269fa443d68cb5b51760466d00c9f8`

Captured at: `2026-07-30T16:19:15.366161Z`

Mode: fixture for capability, fault, concurrency, and recovery behavior;
analysis for dependency, license, secret-pattern, and public-artifact scans.
No external-service behavior is claimed.

Source and tool versions: Python 3.11.15; SQLite 3.53.1; uv 0.11.28; pytest
9.1.1; pip-audit 2.9.0; Retirement Conductor 0.1.0. The lock review covered
20 third-party package records from PyPI with SHA-256-bound source and wheel
artifacts.

Command or operator action:

```text
make check
make test-security
make test-faults
make test-recovery
make scan
make phase07-evidence
git diff --check
```

Expected result: read and plan principals cannot mutate; target and approval
scope remain exact; untrusted source text cannot expand authority; tampered,
stale, conflicting, unavailable, and ambiguous outcomes refuse; reads retry
within a bound while native mutations never retry blindly; backup and restore
reproduce the canonical campaign; a copied store cannot become a second
authority; scans expose any finding instead of silently passing it.

Observed result: `make check` passed all 217 tests, Ruff, formatting, mypy,
repository validation, secret and public-artifact review, source and wheel
builds, and the diff check. The focused security, fault, and recovery targets
passed 93, 72, and 43 tests. The Git/dbt plan-only receipt preserved the
branch and target digest and created no apply artifact. The Looker plan-only
receipt omitted `save_content`, made zero query-creation and PATCH calls, and
retained no hostile source instruction.

The injected read sequence recovered after 429, connection loss, and 503 in
four bounded requests. Six ambiguous mutation cases each made exactly one
request and returned `APPLY_OUTCOME_UNKNOWN`; definitive 401, 403, 404, 409,
422, and 429 outcomes mapped to their stable actionable refusal. Campaign,
gate, repository-isolation, overlap, recreated-identity, compensation, and
tamper cases remained fail-closed.

SQLite online backup published mode `0600` only after integrity,
foreign-key, event-replay, manifest, gate-ledger, and logical-snapshot checks.
Restore at the original bound path reproduced manifest
`sha256:c86a4ea8a8989180c1abe972cbfe2670f51fb8c4f77656d30213561b8ad4e670`
and schema versions 1 through 3. Opening a copied store refused with
`RUNTIME_WRITER_MISMATCH` before changing the database. Diagnostics
deliberately reported the fixture's one stuck campaign as unhealthy, proving
the operational signal is observable rather than masking it.

The final scan audited six runtime and 18 all-group installed packages with
zero known vulnerabilities, accepted the recorded license expressions,
reviewed 20 locked third-party records, checked 270 text files for recognizable
secrets, and reviewed 46 public artifacts. An earlier all-group scan found
the published pytest 8.4.2 advisory; commit `1400a1c` upgraded the constrained
development version to 9.1.1, after which the repeated audit was clean.

Refusal cases: apply-disabled Git/dbt and Looker
(`AUTH_APPLY_DISABLED`); ambiguous native mutation
(`APPLY_OUTCOME_UNKNOWN`); permission denial
(`SOURCE_LOOKER_PERMISSION_DENIED`); missing or recreated identity
(`IDENTITY_NOT_FOUND`, `IDENTITY_NATIVE_OBJECT_RECREATED`); source conflict
(`SOURCE_FINGERPRINT_MISMATCH`); failed validation
(`VALIDATION_RECEIPT_FAILED`); unavailable source
(`SOURCE_LOOKER_UNAVAILABLE`); copied or wrong writer
(`RUNTIME_WRITER_MISMATCH`); campaign overlap
(`SOURCE_CONSUMER_OVERLAP`); compensation conflict
(`COMPENSATION_CONFLICT`); and integrity, provenance, replay, drift, and
unavailable-state gate refusals.

Tracked artifact paths:
`artifacts/public/phase07/security-evidence.json`,
`artifacts/public/phase07/failure-matrix.json`,
`artifacts/public/phase07/recovery-evidence.json`,
`artifacts/public/phase07/scan-evidence.json`, and
`artifacts/public/phase07/phase07-evidence.json`. Their file SHA-256 digests
are, respectively,
`97544b199767de6268948df9bd8043bbfe32e72e5b2cc5b607b2dc2fbcdb089c`,
`0ec74a67bd130d33d8ed697599201edc910a77f919b69097f50bfacd50c81e23`,
`4dd7162ea7e1ec4605b35e1914084d2b34f48376bb0aa12761e5fa21cdd9a6fb`,
`f02972cc85b77433c0bdc78e530fe156268e2c9559c0e4ca81e6b56b760f7acd`,
and
`aca315f18fb50841d7194757b14837033897c5c776f3bf614481f30bbec59b28`.
The canonical phase evidence digest is
`sha256:43b5b2d44631df04f8a08c643b4c65f9524ba7854a17447fcf09f87e2275e8a0`.

Private artifact digests: the ignored final scan file was byte-identical to
the tracked redacted scan evidence with file SHA-256
`f02972cc85b77433c0bdc78e530fe156268e2c9559c0e4ca81e6b56b760f7acd`
and canonical scan digest
`sha256:2108dab4cc7d54d36275693404c6bc1b4699b85491b2a4036a25e794d5d0a7e2`.
Focused command output is retained only by its three digests in the phase
summary; disposable recovery stores and injected transport responses were
deleted after promotion.

What this proves: the supported local single-writer runtime, Git/dbt boundary,
deterministic Looker boundary, producer gate, evidence artifacts, dependency
set, and recovery procedure withstand the recorded credential-independent
security and reliability probes without producing false readiness or leaking
the injected secrets. The deployment contract can distinguish plan from
apply and a valid backup from a second campaign authority.

What this does not prove: live Looker permissions or service behavior; a live
Looker timeout, cancellation, rate limit, partial mutation, compensation, or
concurrent attempt; production host or secret-provider security; distributed
storage; arbitrary filesystem classification; binary reproducibility; signed
package provenance; or completeness of a point-in-time advisory and static
secret scan. This entry is historical and no longer determines current Phase
07 acceptance.

### Phase 07 post-removal acceptance

Tested behavior commit: `6e4ca870106c5f65c894df0dce8024a62395c787`

Mode: deterministic local fixtures for capability, fault, concurrency, and
recovery behavior; analysis for dependency, license, secret, and public
artifact scans; direct binding to the live-local Phase 06 evidence digest.

Commands:

```text
make phase07-evidence
generator: make test-security; make test-faults; make test-recovery
generator: security scan; public-artifact review; secret scan
```

Observed result: security, fault, and recovery targets passed 53, 47, and 40
tests. A plan-only Git/dbt principal refused with `AUTH_APPLY_DISABLED` while
the branch, target digest, and artifact directory remained unchanged. The
failure matrix retained integrity, overlap, partial DataHub, unavailable
MCP/API, hostile repository, interrupted Git, and producer-gate cases as
refusal or contained outcomes. The receipt binds to Phase 06 digest
`sha256:b930045d5769c9b7d938f5079dd4a37e4621b23796a0fdf45ad2ddd34e20e4b9`,
which records zero false readiness and one producer sentinel.

The mode-`0600` backup reproduced canonical manifest
`sha256:c86a4ea8a8989180c1abe972cbfe2670f51fb8c4f77656d30213561b8ad4e670`,
evidence envelope, logical snapshot, and schema versions 1 through 3 after
original-path restore. A byte-valid copied store refused with
`RUNTIME_WRITER_MISMATCH` before database change. Diagnostics deliberately
reported the one stuck fixture campaign rather than masking it.

The scan found zero vulnerabilities in six runtime and 18 all-group packages,
accepted all 18 reviewed package licenses, verified 20 SHA-256-bound lock
records, scanned 302 text files for secrets, and reviewed 56 public artifacts.
The canonical Phase 07 evidence digest is
`sha256:38ca5631665d6b3402b8b07226c49a3531490a6e3adcb95053d4e671c432cc23`;
the tracked summary file SHA-256 is
`24472c78ac7cba8215c89e7dd9c4576bfb44c698c07abada719af07585b1727e`.

Reviewer inspection: inspected every focused test count and output digest;
plan-only state; benchmark binding; all six failure categories; backup,
restore, copied-store, schema, and diagnostics fields; vulnerability, license,
lock, secret, and public-artifact results; limitations; all five artifact
digests; and tracked whitespace.

Limitations: failure injection is deterministic and local; the advisory
result is point-in-time; static secret patterns are not proof of universal
absence; and production host, identity, secret-provider, storage, and signing
controls remain deployment responsibilities. These limitations do not weaken
the supported local product claim. `EP-007` is complete.

Reviewer inspection: verified all five canonical artifact digests and file
digests; inspected plan-only mutation counts, required permissions, retry
counts and delays, every mutation refusal, backup mode, restored manifest and
schema versions, copied-store preflight order, unhealthy diagnostic signal,
package/version/license findings, vulnerability counts, scan limitations,
live-boundary wording, tracked public content, secret-scan result, and
generated whitespace.

### Historical Phase 08 pre-removal observations

These observations cover the earlier Phase 08 engineering tasks at their
recorded commit. They were superseded by the post-removal acceptance below;
independent operator and customer-value mode remains `NOT_RUN`.

Evidence ID: EP-008 (credential-independent portion)

Requirement IDs: RC-017; preparation and an explicit unsatisfied boundary for
RC-018

Repository behavior and tested commit:
`eb7206708c145e4d8a50200fb6105a60207cb515`

Tracked evidence commit:
`4411e8b`

Captured at: `2026-07-30T18:21:02.772304Z`

Mode: live for the disposable loopback DataHub Core, MCP, Git, dbt, DuckDB,
publication, and producer-sentinel path; fixture for built-in reference,
clean-install state, upgrade, rollback, removal, and copied-state behavior;
analysis for package inspection, compatibility, documentation, and the
operator boundary. No independent operator result is
claimed.

Source and tool versions: Retirement Conductor 0.2.0; Linux x86_64 with glibc
2.43; CPython 3.11.15, 3.12.13, 3.13.14, and 3.14.4; uv 0.11.28; Git 2.53.0;
bubblewrap 0.11.1; Docker client 29.1.3; dbt-core 1.12.0; dbt-duckdb 1.10.1;
DuckDB 1.5.5; DataHub GMS v1.6.0 image
`sha256:672bceed7f36f751ab3302c30826c6ba124d1c0fd8d24c3724e725078b864018`;
and MCP 0.6.0 at clean source commit
`9a6946daa7d30eb481c82dd8ee5e15ae6526a3c9`.

Command or operator action:

```text
make check
make package
make test-install
make test-upgrade
make test-reference-campaign
git diff --check
make phase08-evidence
```

Expected result: one reviewable release installs without source-checkout
imports; missing configuration names its exact references without values; the
built-in fixture remains blocked; the installed product completes the
Core/Git/dbt path; upgrade and backup-based rollback preserve the campaign;
copied state refuses; removal requires exact confirmation and remains separate
from package uninstall; compatibility and optional boundaries are labeled
honestly; local metrics have no implicit or remote collection; and no
independent-operation claim is made without a real operator.

Observed package and install result: the 0.2.0 wheel contained 63 members and
had digest
`sha256:415d7efb71ee0059e0831b3347fa48fcade7ffab2c835b35428cfa74e04d741b`.
The 72-member source archive had digest
`sha256:b5f3cad1aaaff2373e28505a3036da6eb94363531cdf6af92c7f889c33b90f25`,
excluded operational status, evidence, tests, scripts, and runtime state,
reproduced byte-for-byte, and rebuilt the wheel byte-for-byte. Runtime
requirements were hash-bound; a CycloneDX 1.5 SBOM and checksum manifest were
inspected. The package remains unsigned, and the evidence says so.

Four clean virtual environments imported only their installed wheels. Each
reported the five missing Core/Git/dbt configuration references under
`RUNTIME_CONFIGURATION_INCOMPLETE`, reproduced the same built-in reference
manifest
`sha256:16fa6dce7cd313fa63a3da55701db39e89eaef3f7833c09643ea867f78cacec3`,
and kept it `BLOCKED` with `EVIDENCE_MODE_NOT_LIVE`. The Python 3.11 removal
run rejected a byte-valid copied store with `RUNTIME_WRITER_MISMATCH` before
creating a lock or changing the copy, rejected unconfirmed deletion with
`AUTH_APPROVAL_MISSING`, removed only the exact confirmed state, retained the
ignored plan, then removed the console entry point through the package
manager.

Observed lifecycle result: upgrading the package from 0.1.0 at
`30173f160c3c87a8daf0a3c1988c7ccde10662ec` to 0.2.0 advanced schema versions
from `[1]` to `[1, 2, 3]` without changing manifest
`sha256:cc3400464ed98cd6afed3a1e5e1ccd0d8cc157b5872473b4ebe06cc2cf1d02d7`.
The verified pre-upgrade database plus prior wheel restored that same
manifest and byte-identical prior database; in-place downgrade remained
explicitly unsupported.

Observed live reference result: installed deployment preflight passed the
`core-git-dbt` profile with one writer, all five named references, Git,
bubblewrap, Docker, and dbt present. Local metrics were explicitly opted in
for the test while `remote_export` remained false. DataHub Core and MCP were
healthy on loopback. All 34 product operations used the installed wheel and
zero used the source checkout. Native dbt parse, seed, build, and semantic
test passed. The isolated one-consumer campaign reached
`READY_TO_RETIRE`, verified its publication read-back, and wrote exactly one
producer sentinel. A late second consumer reopened it to `UNSAFE`; the
31-consumer rich graph remained `UNSAFE` and the producer gate refused with
`GATE_DECISION_NOT_READY`. The gate ledger recorded one executed and 12
refused attempts.

The final tracked-evidence check passed 228 tests, Ruff, formatting, strict
mypy, 164-file repository validation, a 294-file secret scan, a 53-file
public-artifact review, source and wheel builds, and `git diff --check`.

Refusal cases: missing deployment configuration
(`RUNTIME_CONFIGURATION_INCOMPLETE`); fixture policy
(`EVIDENCE_MODE_NOT_LIVE`); copied deployment state
(`RUNTIME_WRITER_MISMATCH`); removal without exact digest confirmation
(`AUTH_APPROVAL_MISSING`); late and opaque consumers (`UNSAFE`); and producer
gate refusal (`GATE_DECISION_NOT_READY`). The operator artifact returns
`NOT_RUN` and `NOT_SATISFIED`, rather than a synthetic pass.

Tracked artifact paths:
`artifacts/public/phase08/package-evidence.json`,
`artifacts/public/phase08/install-evidence.json`,
`artifacts/public/phase08/upgrade-evidence.json`,
`artifacts/public/phase08/reference-evidence.json`,
`artifacts/public/phase08/compatibility-evidence.json`,
`artifacts/public/phase08/operator-boundary.json`, and
`artifacts/public/phase08/phase08-preacceptance-evidence.json`. Their file
SHA-256 digests are, respectively,
`7d3d8ef482f1b5a9fa5c35f0725f890875fadaa3814d052d59e42fe3222dedea`,
`9463c5a4a3cf76a68a6b807045be71ec4c23692fe70e312cf1cef18f3c51cc02`,
`ebe127be08d1d58a3f63f3aacbf4055e4334094039817c9e4edb4188e45bc0cd`,
`8ddf5f10c11ea490d619e940013e545df1f84704bde528f6a55406d04f521866`,
`92bef59564042612d3554f91bc2ab49b5a80a8f090400c6a5d12f525ccf7da09`,
`de57f07d41cee6ed21fb7947a167ad4bb5f087e207675c3de2c5c7850224e878`,
and
`41e8f9a5051332618dcc2215b568a35d24ae0f1c4c73ce0ed1ec72d68d63dc0b`.
The canonical phase pre-acceptance digest is
`sha256:15b3449da0397e7dc365c69487ac9a239b9e005398ab9c5b28f28716844fa7e0`.

Private artifact digests: the ignored raw package, install, upgrade, and
reference files had SHA-256 digests
`4e80e40f19c59479e701f0b4db59512f9f9bc1cadde3c11237bde582b7520e3a`,
`b700801c2aba10fe864906861f6d3f8413c6a2b788d7eb2e18135207a8d188dd`,
`1517c80ce57e757221e2ed9e30e235890f4c954895439d6d06674801d6fad5a9`,
and
`4f941099340c1eab09427d048020dc822b9c66407ecef42fcfc671221dc7cc59`.
Their canonical artifact digests were
`sha256:7ae90d294996ca67b16ab84afc9e59b53cc15a0c2cbec40d3777cad587427624`,
`sha256:e83d0203e3d945e7a1d2300f6196eaabeca97cb16e3e371e7749bc2e00e3f97a`,
`sha256:1ae695d1bd32bf7d7451f5e6a48e0b8fba05428959cc9bb9ed02625b907463d0`,
and
`sha256:7eae72bdd6dff2039fd4fe66c784b86fbcfa7d6e75b72043a3c0a5efc677a387`.
Raw clean-environment directories, campaign databases, backups, native
content, and command logs were removed or retained only under ignored local
state.

What this proves: another clean Python environment can install the bounded
single-writer product artifact, diagnose missing configuration, reproduce the
fixture decision, execute the complete first vertical against disposable
live Core through the installed entry point, preserve and restore campaign
state across an upgrade, refuse copied authority, and remove only confirmed
state. The repository now supplies an executed compatibility boundary and a
complete independent-evaluation protocol.

What this does not prove: an independent person can operate the runbook; that
the workflow is frequent or valuable enough to adopt; a buyer exists;
DataHub Cloud behavior; macOS, Windows, musl, shared-state, or product
container support; signed release provenance; or any live Looker identity,
mutation, native validation, compensation, ingestion, or failure behavior.
Phase 08 and `EP-008` therefore remain access-dependent.

Reviewer inspection: verified every raw and public canonical digest and file
digest; compared one package identity across all four receipts; listed the
wheel and source archive; checked source-archive exclusions and rebuild;
inspected all Python versions, isolated imports, missing-reference names,
fixture digests, schema versions, manifest parity, backup digests,
copied-state ordering, removal receipt, package uninstall, service health and
identity, installed/source operation counts, native validator result,
publication settle attempts, gate counts, all decisions and refusals, local
metrics boundary, executed/not-executed compatibility rows, operator
`NOT_RUN` state, repository validation, and public/secret scans.

### Phase 08 post-removal engineering acceptance

Evidence ID: EP-008 (credential-independent engineering portion)

Requirement IDs: RC-017; explicit unsatisfied follow-on boundary for RC-018

Tested behavior commit: `c3440b2702c78de0f3b7651271ebbe5f750ec801`

Captured at: `2026-08-02T22:14:54.463223Z`

Mode: live local for loopback DataHub Core, MCP, Git, dbt, DuckDB,
publication, and producer gate; fixture for clean-install state, reference,
upgrade, rollback, removal, and copied-state behavior; analysis for package,
compatibility, documentation, and the operator boundary. No independent human
result is claimed.

Source and tool versions: Retirement Conductor 0.2.0; Linux x86_64 with glibc
2.43; CPython 3.11.15, 3.12.13, 3.13.14, and 3.14.4; uv 0.11.28; Git 2.53.0;
bubblewrap 0.11.1; Docker 29.1.3; dbt-core 1.12.0; dbt-duckdb 1.10.1; DuckDB
1.5.5; DataHub Core v1.6.0 image
`sha256:672bceed7f36f751ab3302c30826c6ba124d1c0fd8d24c3724e725078b864018`;
and MCP v0.6.0 at clean source commit
`9a6946daa7d30eb481c82dd8ee5e15ae6526a3c9`.

Commands:

```text
make package
make test-install
make test-upgrade
make test-reference-campaign
make phase08-evidence
```

The evidence generator additionally ran `make check`, `git diff --check`, the
secret scan, and the public-artifact review.

Observed package result: the 76-member wheel digest is
`sha256:17e63b4c714362469268659ee39809319371958c415dc6209580540dd9b1d5f0`.
The 85-member source-archive digest is
`sha256:9d70c9caedaa78e114875a7b06bd73f86fad172f12257ed67551246146a1576a`.
Both rebuilt byte-for-byte, the source archive rebuilt the same wheel, the
runtime lock was hash-bound, and operational state was absent. Listing both
archives found no deprecated adapter module, schema, recipe, fixture, or
modeling-language file. The package remains unsigned and says so.

Observed install and lifecycle result: isolated Python 3.11 through 3.14
environments imported only the installed wheel, reproduced the same blocked
fixture, and named all five missing Core/Git/dbt configuration references
without values. Copied state refused unchanged, unconfirmed removal refused,
confirmed state and package removal passed, and the removal plan remained.
Upgrade from 0.1.0 advanced schema versions `[1]` to `[1, 2, 3]` without
changing manifest
`sha256:cc3400464ed98cd6afed3a1e5e1ccd0d8cc157b5872473b4ebe06cc2cf1d02d7`;
backup-based rollback restored that same manifest and prior pair.

Observed live reference result: all 35 product operations used the clean
installed wheel and zero used the source checkout. Preflight passed the
`core-git-dbt` profile with one writer and local-only metrics. DataHub Core
and the exact MCP v0.6.0 executable were healthy on loopback. Native dbt
parse, seed, build, and test passed. The isolated campaign reached
`READY_TO_RETIRE`, verified publication read-back after two attempts, and
wrote one sentinel. The late two-consumer campaign reopened to `UNSAFE`; the
41-consumer rich graph stayed `UNSAFE`; its gate refused with
`GATE_DECISION_NOT_READY`. The ledger recorded one executed and 12 refused
gate attempts.

Validation result: `make check` passed 183 tests, Ruff, formatting, strict
mypy, 174 required-file and 146-link validation, the 302-file secret scan,
the 56-file public-artifact review, source and wheel builds, and
`git diff --check`.

Tracked artifact paths and file SHA-256 digests:

- `artifacts/public/phase08/package-evidence.json` —
  `9da77d191d71532751d05c923293c800ce05c441c03bdc374037ce7eb56c2882`;
- `artifacts/public/phase08/install-evidence.json` —
  `47cf4841790292b71cfc84580476531102ee858dbb23faad33cc45400559ff21`;
- `artifacts/public/phase08/upgrade-evidence.json` —
  `84fc47f3764c301f78260212606435e11d5a88f4fa24f0acbd5ce1b35f9388d6`;
- `artifacts/public/phase08/reference-evidence.json` —
  `9bff5f9096dbc99c2cefaff675cc3bc4e72026aead88fa8120f1b8431eb8448d`;
- `artifacts/public/phase08/compatibility-evidence.json` —
  `aacc3ad33cf92111ec0583835699a511971def6b0af907761640fbbade9f85b1`;
- `artifacts/public/phase08/operator-boundary.json` —
  `3f38685f20a4bd7372b3748b526b6de507b122ed9c114e00b022ccd954280030`;
- `artifacts/public/phase08/phase08-preacceptance-evidence.json` —
  `de6bd5952d45041e9dc4b79909bbaacc494b8f88143badbd652a24525f54e2c6`.

The canonical engineering-acceptance digest is
`sha256:c7b6b754380f3c01c411db7b847959e02bea2f8bfe0f8856bb144a4db5876d05`.
Ignored raw package, install, upgrade, and reference file SHA-256 digests are,
respectively,
`6970f56d3b656995db09dcaf3d4f878821f360b7070289c63337e1e6321506a1`,
`7c9a95c567a3e3ff97abbc6012680565fd05946bdc199ed1e908c337e7b83e46`,
`dd4c96403a1328fdbe31e9d1b370d6723aec52708c7d9cc920bd2c81c58cdf2b`,
and `b9e40bdd6e65c425dc84916791dffb65c07e1287a1b2e318d9d228e97e02d8b5`.

What this proves: the narrowed post-removal release is reproducible,
installable, migratable, recoverable, removable, and capable of executing the
complete supported DataHub plus Git/dbt vertical entirely through its clean
installed entry point while preserving refusal behavior.

What this does not prove: independent operation, recurring customer value,
buyer willingness, DataHub Cloud, non-Linux hosts, shared or multi-writer
state, a product container, release signing, or production coverage. The
operator artifact truthfully remains `NOT_RUN` and `NOT_SATISFIED`; RC-018 is
a follow-on requirement and no adoption claim is made.

Reviewer inspection: inspected every raw and public digest; archive member
lists and absence check; one package identity across all receipts; four Python
versions; isolated imports; actionable missing references; fixture decision;
schema and manifest parity; backup, copied-state, removal, and uninstall
fields; exact Core image and MCP tag/commit/version; installed/source operation
counts; dbt result; publication attempts; ready, late, and rich decisions;
gate counts; compatibility exclusions; operator non-claim; broad validation;
and tracked whitespace. The credential-independent Phase 08 engineering
boundary is complete.

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

## EP-004 — phase 04 reconciliation and producer gate

Evidence ID: EP-004

Requirement IDs: RC-007, RC-011, RC-012, RC-013

Repository commit: `25466a9085d4e3beea194616a76b40e0a9a14f5c`

Captured at: `2026-07-30T12:45:46Z`

Mode: live positive and refusal paths against disposable sources, supplemented
by fixture contract tests.

Source and tool versions: DataHub Core v1.6.0; self-hosted DataHub MCP server
0.6.0; Git 2.53.0; dbt-core 1.12.0; dbt-duckdb 1.10.1; DuckDB 1.5.5; SQLite
3.53.1 in the uv runtime; Python 3.11.15; uv 0.11.28; Retirement Conductor
0.1.0.

Command or operator action:

```text
make test-end-to-end
retirement-conductor campaign reconcile --campaign <isolated-live-id> ...
retirement-conductor campaign publish --campaign <isolated-live-id> ...
retirement-conductor campaign verify-publication --campaign <isolated-live-id> ...
retirement-conductor producer plan --campaign <isolated-live-id> ...
retirement-conductor gate --campaign <isolated-live-id> ...
retirement-conductor gate --campaign ret-orders-git-dbt ...
make phase04-evidence
make check
git diff --check
```

The end-to-end runner supplied a unique ignored store, repository, campaign,
writer, trusted run, and sentinel root. It invoked each listed CLI command
directly, captured exact JSON and exit status, restored the DataHub baseline,
and then ran the focused policy, gate, and store tests. The evidence exporter
reverified every retained digest and ran 61 focused DataHub, Git/dbt, policy,
gate, and store tests. The final `make check` passed all 138 tests, repository
validation, secret and public-artifact scans, source and wheel builds, and
the diff check.

Expected result: equivalent live before/after scope; bounded observable
refresh; one all-closed isolated campaign reaching `READY_TO_RETIRE`; exact
stable DataHub publication and read-back; one short-lived issued producer plan
executing one harmless sentinel; a new consumer reopening the campaign; a
31-consumer rich graph remaining `UNSAFE`; and every missing, drifted,
tampered, stale, untrusted, delayed, alternate, or replayed authorization
failing closed.

Observed result: the isolated campaign recorded one baseline consumer and one
validated Git/dbt receipt. Ready reconciliation used equal scope digest
`sha256:df758c990c8940c414bd002dba3493f96e425dc47d9a4907bda524821ff36be2`,
observed refresh on its first bounded attempt, and produced comparison
`sha256:e6a86d0de5d2c55b5004e641a9994dc3b7a1b2ecb77995a684a7b6e7700b0f53`.
DataHub published that reconciled manifest and exact read-back produced
canonical ready manifest
`sha256:5b7c72d7febcb5d5bf4c6d547ebcb6cc720264a8f5f5e081a1849d229bfb54f2`.

Producer plan
`sha256:de6a134022b54eafd099afa33cffe2c2625e2b7f558d02b3c24449a78168b8ee`
was durably issued for that manifest. The gate recorded intent, reread the
bound sources and publication, wrote one sentinel, and recorded receipt
`sha256:dd7a87f4031f735358d017050aca7e394178be69b97ee134618f9ae5f27070ed`.
The inspected ledger contained schema migrations 1 through 3, 13 attempts,
exactly one `EXECUTED`, 12 recorded `REFUSED`, and no second action.

A live degree-two consumer then increased current membership from one to two
under the same scope. Comparison
`sha256:69269f775693bbb5810e262228bdb2c176a8bc1bbf30c2fc73e552b487afe54e`
listed exactly one added identity. After updating the same DataHub document
and verifying read-back, canonical manifest
`sha256:f301e730cda6949969fcf7657aab5f6172719665daef5f56ee734df5b639fece`
was `UNSAFE` with `RECONCILIATION_NEW_CONSUMER` and
`POLICY_CONSUMER_OPAQUE`; its gate refused and sentinel count remained one.
The separate rich campaign returned 31 consumers, stayed `UNSAFE`, and also
refused. The deterministic matrix produced exactly `BLOCKED`, `UNSAFE`,
`REVIEW_REQUIRED`, and `READY_TO_RETIRE`.

Refusal cases: missing approval (`AUTH_APPROVAL_MISSING`); untrusted or wrong
run (`GATE_PROVENANCE_UNTRUSTED`); wrong writer
(`RUNTIME_WRITER_MISMATCH`); missing campaign state
(`RUNTIME_CAMPAIGN_NOT_FOUND`); unavailable DataHub
(`SOURCE_DATAHUB_UNAVAILABLE`); configuration, validator, or authorization
drift (`GATE_STATE_DRIFT`); changed consumer file
(`SOURCE_GIT_FILE_CHANGED`); changed producer source (`GATE_SOURCE_DRIFT`);
tampered validation (`INTEGRITY_DIGEST_MISMATCH`); changed replacement schema
(`SPEC_REPLACEMENT_INCOMPATIBLE`); replay (`GATE_PLAN_REPLAYED`); and late or
rich non-ready state (`GATE_DECISION_NOT_READY`). Focused tests additionally
covered stale and partial evidence, disappeared unclosed consumers, unissued
and expired plans, missing verified publication, and outcome-unknown action.

Tracked artifact paths:
`artifacts/public/phase04/ready-manifest.json`,
`artifacts/public/phase04/late-manifest.json`,
`artifacts/public/phase04/reconciliation-evidence.json`,
`artifacts/public/phase04/gate-evidence.json`,
`artifacts/public/phase04/refusal-evidence.json`, and
`artifacts/public/phase04/phase04-evidence.json`.

Private artifact digests: complete ignored run summary
`sha256:8d06d08d84e6067b6ac34df1731b52f999c7bf5449247dca931a5d3b9a5fb5fe`;
ready and late reconciliation comparisons
`sha256:e6a86d0de5d2c55b5004e641a9994dc3b7a1b2ecb77995a684a7b6e7700b0f53`
and
`sha256:69269f775693bbb5810e262228bdb2c176a8bc1bbf30c2fc73e552b487afe54e`;
producer plan
`sha256:de6a134022b54eafd099afa33cffe2c2625e2b7f558d02b3c24449a78168b8ee`;
gate receipt
`sha256:dd7a87f4031f735358d017050aca7e394178be69b97ee134618f9ae5f27070ed`;
sentinel
`sha256:122df7f835c626d0d0e584fbbd8a0036eb8399057ac44e93ce18bf08240b77ae`;
and rich snapshot
`sha256:192cbbac0ba7368c66129f9db7bf84fdcfb6ebffdba0d7ad811662c91d743498`.
Individual command-output digests are retained in the tracked refusal
evidence.

The tracked artifact file SHA-256 digests are, respectively,
`e260444a1afe49604eaa42c06f28463e7b62e400617dfc1dd8685d2640e18012`,
`a5725f919f918754198f1f77abbf17aed46b4ef4141479d9ae37f74f05b7570a`,
`2245cc32225a7829bf6fe1ecb55a6761eb200082397dc5b846a9e75b3f51fd30`,
`5890a08d7a0d4b4068a039f4f36ab0de91ee51979e761d34175fdc19d1443312`,
`3dee6fb10174f850d56f2cf16e82506e082377464f39f7cf60157b5f10a89c1c`,
and
`86907b965314fd0b31140ba191a661f0a56028b5e0570f7d7c9d2cd5ebc6d2f1`.

What this proves: the first supported product vertical runs end to end through
live catalog discovery, authorized source mutation, native validation, fresh
equivalent reconciliation, stable DataHub write/read-back, deterministic
policy, and an enforceable one-time producer action. A later graph consumer
and the consequential rich graph both reverse or prevent that action.

What this does not prove: production or authenticated DataHub behavior,
universal catalog completeness, a real ingestion connector's ordering, a
warehouse deletion, production CI identity, Looker execution, or safety
outside the recorded evidence envelope. The producer action is deliberately a
local sentinel and DataHub Core did not expose `isPartial`.

Reviewer inspection: inspected baseline/current scope and counts, bounded
refresh receipts, ready and late membership diffs, all manifest and
publication digest links, stable document identity, DataHub lifecycle
non-mutation, producer source and trusted-run bindings, issued-plan and attempt
ledger, exact sentinel count and digest, every live refusal payload, rich
inventory result, four-way decision matrix, 61-test focused result, public
artifact scan, and secret scan.

## EP-005 — phase 05 operator experience

Evidence ID: EP-005

Requirement IDs: RC-013, RC-014

Repository commit: `ae62486ce85e14f9328d69d840325da7d728df09`

Captured at: `2026-07-30T13:51:09Z`

Mode: live-derived canonical state from the disposable phase 04 campaign plus
deterministic fixtures; real local browser execution. No new DataHub or native
source mutation was claimed by this phase.

Source and tool versions: phase 04 DataHub Core v1.6.0 and Git/dbt canonical
manifests; Python 3.11.15; uv 0.11.28; Retirement Conductor 0.1.0; Playwright
CLI 0.1.17; synchronized Chrome major 150 browser/driver; axe-core 4.10.3.

Command or operator action:

```text
retirement-conductor campaign inspect --campaign <phase04-id> ...
retirement-conductor campaign explain --campaign <phase04-id> ...
retirement-conductor report build --campaign <phase04-id> ...
make phase05-browser
make phase05-evidence
make test-ui
make check
git diff --check
```

The exact store-backed inspect, explain, and report commands were run against
the reopened phase 04 campaign. The evidence promoter also rendered portable
canonical manifests for all four final decisions and ran secret,
public-artifact, determinism, and structural accessibility checks. The browser
harness served only local self-contained reports, tabbed through every
interactive control, activated native disclosures with Enter, captured
desktop and mobile screenshots, measured layout, counted external requests,
and ran axe in each page.

Expected result: the first view states target, replacement, current decision,
consumer and open-condition counts, bounded evidence coverage, next action,
and exact manifest digest. Expanded views retain source scope, freshness,
pagination, limitations, native action, receipt state, stable condition code,
evidence source, and safe recovery. CLI and HTML agree; unknown coverage never
looks complete; stale never looks validated; plan and apply remain separate;
public export is structurally redacted; keyboard, mobile, and accessibility
checks pass.

Observed result: `BLOCKED`, `UNSAFE`, `REVIEW_REQUIRED`, and
`READY_TO_RETIRE` CLI outputs each retained their canonical decision and
digest. The store-backed live command showed two consumers, one closed, one
open, two blockers, complete-within-scope evidence from two required sources,
and the exact late manifest digest
`sha256:f301e730cda6949969fcf7657aab5f6172719665daef5f56ee734df5b639fece`.
Its expanded output named both source limitations, the validated and missing
receipt states, `POLICY_CONSUMER_OPAQUE`,
`RECONCILIATION_NEW_CONSUMER`, their evidence sources, and recovery actions.

Three reports reproduced byte-for-byte: live refusal
`sha256:64719fe09dfd58050fada852b4c7eb9d14c9b45e59ea7c6da70c635e41a32b1c`,
all-closed fixture
`sha256:b3e63e925d3adb1b9e56a7fb5acd996a5c14a309c03f9b9d98e0bc8dc44f8631`,
and public export
`sha256:ae887766b5f308e04157be998fdd4986fbbdc0ede7907a9319a33fe18a42f0be`.
The all-closed consumer was visibly `VALIDATED`, but the fixture campaign
remained `BLOCKED` with `EVIDENCE_MODE_NOT_LIVE`.

At 1440 pixels and 360 pixels, measured content width equaled viewport width,
external request count was zero, and all 15 links and disclosures were
keyboard reachable; both Enter disclosure probes succeeded. Axe-core reported
35 passing rule groups per page, zero violations, and zero incomplete checks.
The deterministic WCAG 2.2 AA structural subset passed three reports,
including contrast ratios from 5.19:1 through 15.62:1. The final desktop and
mobile screenshots were inspected after the last regeneration. The closure
`make check` passed all 151 tests, Ruff, formatting, mypy, repository
validation, secret and public-artifact scans, source and wheel builds, and the
diff check.

Apply requires `--confirm-plan-digest` in addition to durable approval.
Focused integration coverage proved missing approval or confirmation refuses
as `AUTH_APPROVAL_MISSING`, while a different digest refuses as
`AUTH_APPROVAL_WRONG_PLAN`; the phase 04 live runner passed the exact reviewed
digest.

Refusal cases: missing apply confirmation or approval
(`AUTH_APPROVAL_MISSING`); wrong confirmed plan
(`AUTH_APPROVAL_WRONG_PLAN`); fixture evidence
(`EVIDENCE_MODE_NOT_LIVE`); opaque and late consumers
(`POLICY_CONSUMER_OPAQUE`, `RECONCILIATION_NEW_CONSUMER`); unknown evidence
coverage; stale receipt; digest or schema-invalid manifest; attempted HTML
injection; traversal-shaped report filename; and public source/principal,
field, limitation, or secret-like content.

Tracked artifact paths: `artifacts/public/phase05/phase05-evidence.json`,
`artifacts/public/phase05/browser-evidence.json`,
`artifacts/public/phase05/accessibility-evidence.json`, the five
`cli-*.txt` summaries, three generated reports,
`artifacts/public/phase05/review-required-manifest.json`, and the two
screenshots under `docs/assets/phase05/`.

Private artifact digests: ignored raw axe result
`sha256:7a9d131795325fc27ae2f53a0ee993cd2e08fd074c03162625b85a14109326d6`;
canonical browser evidence
`sha256:45be7e089b451e58f6220ad15c2bb75d452826c643699bb5c5bd93f36dc2a655`;
canonical accessibility evidence
`sha256:f634ee5a52d7051b6f13fb1ac6f8a466dbad99dad1f9b71c938b7fc4dae99e90`;
and phase evidence
`sha256:05aeb6bdb606db132f0ac255ce329dae82d30ab4d691f5599a822776b94debaf`.
The tracked phase evidence file SHA-256 is
`0e80d0d32839d20220e97b6fdd3de887b645161d41dbc1a6baaa673654c83072`.

What this proves: a single verified canonical state supplies mutually
consistent terminal and report decisions, bounded evidence explanations,
native receipt distinctions, actionable refusal recovery, and explicit plan
confirmation. The generated view is deterministic, self-contained,
responsive, keyboard operable, automatically audited, and structurally
redactable without becoming a second policy or authorization layer.

What this does not prove: independent nontechnical comprehension, production
browser policy, universal assistive-technology behavior, authorship from a
digest, a newly executed source mutation, a production DataHub boundary,
Looker operation, or safety outside the displayed evidence envelope.

Reviewer inspection: inspected all four CLI decisions and manifest digests;
the exact store-backed live inspect/explain/report output; live refusal,
all-closed fixture, and public HTML; deterministic twin digests; explicit
fixture and limitation language; validated versus missing/stale receipt
rendering; plan confirmation tests; public and secret scans; final desktop and
mobile screenshots; keyboard focus order and disclosure activation; measured
overflow and external requests; axe results; structural/contrast results; and
generated whitespace via staged `git diff --check`.

## Post-goal MCP agent orchestration evidence

Tested behavior commit: `0d70db9b8cb3dbfde0b1c56ca7b37d31800db605`

Mode: ephemeral Codex model trace over retained Phase 04 live-local campaign
state. This is orchestration and explanation evidence; it is not a fresh
DataHub read, production operation, or independent customer observation.

Commands:

```text
make agent-acceptance
uv run python scripts/check_public_artifacts.py
uv run python scripts/check_secrets.py
```

Observed result: Codex CLI 0.145.0 called exactly the two declared Retirement
Conductor MCP tools, `explain_retirement_campaign` and
`inspect_retirement_campaign`, with no shell calls and no unexpected MCP
server. The existing deterministic campaign view reported two consumers: one
closed and natively validated, one open and opaque. The decision remained
`UNSAFE` with `POLICY_CONSUMER_OPAQUE` and
`RECONCILIATION_NEW_CONSUMER`. The model plainly refused producer retirement,
did not attempt the producer action, and named native migration or verified
closure plus fresh equivalent reconciliation as the safe recovery.

The promoted artifact is
`artifacts/public/agent/agent-acceptance.json`, with evidence digest
`sha256:af4450ba95e35260bef253d7133a23c543573fda99283440367d32db2ef6596b`.
The ignored raw JSONL trace is bound by digest
`sha256:79caa77e86d4f6bc4077152a2405250f10a3ce75517e5770381bfc6e9dbfaef5`
but is not public because model traces can contain private runtime details.
The artifact binds back to retained live Phase 04 evidence digest
`sha256:5824e1d9440f01ce07d5531c3e1b586bdbfd79545a4d801b0c34b434a395762e`
and late manifest digest
`sha256:21b394099faa38d10eedd6da6a63142793722b1f79d414bdd5ea78ae4c8428ff`.

Failure observation: the first acceptance attempt called the same safe tool
set in the opposite order from the runner's initial hard-coded expectation.
The runner refused to promote evidence. Commit `0d70db9` corrected the test to
require each exact tool once while preserving observed order; it did not relax
the no-shell, no-extra-server, blocker, decision, or producer-action checks.

Upstream evidence: the same audit reproduced a DataHub MCP lineage pagination
defect and opened issue #194 plus PR #195 with a failing-before/passing-after
test. It also implemented existing issue #192 as PR #196 with a regression
test for deployment-gate diagnostics. Both PRs are external and open; this
ledger does not claim merge, maintainer acceptance, or live CI success.

What this proves: a real model can discover and use the bounded MCP interface,
read the canonical decision, explain a late-consumer reversal, and stop before
a producer action. The model remains outside authorization and policy.

What this does not prove: a fresh source inventory, model determinism,
production safety, independent adoption, automatic closure of the Spark
consumer, or any mutation beyond the established disposable Git/dbt and
sentinel evidence.

## Post-goal complete MCP agent execution evidence

Tested behavior commit: `de5f8958d35c53a36ff557c193d5a793ac9870ff`

Mode: five-stage Codex product-agent run over disposable live-local DataHub
Core and a disposable Git/dbt repository. The user explicitly directed the
separate outer operator to record the exact authorization returned by the
product agent. This is author/operator evidence, not independent RC-018
evidence.

Observed result: the product agent inspected DataHub, created campaign
`ret-orders-agent-1930ce52b2a7`, inventoried one exact dbt consumer, and planned
only `models/orders_isolated_model.sql` at plan digest
`sha256:5ad1502b87870f7356b64d9862c06605cb7f647af6af0cb6a5ad5b6d97a607a1`.
It stopped at `HUMAN_AUTHORIZATION_REQUIRED`; no authorization-recording MCP
tool existed. After the external operator action, the agent applied the exact
target and dbt parse, seed, build, test, and semantic-equivalence validation
passed. The Change Receipt digest was
`sha256:ff136144f091149f3bae1e1d4867e9bf365908f299e17ffaffa522e6e2d2a810`.

Fresh equivalent reconciliation found the one unchanged validated consumer.
The campaign summary was published to DataHub and verified on first read-back.
The ready manifest digest was
`sha256:1e081b9b81efebc14502a5258f6096e6e0b8328dff8c96d2f228c42edb04ed83`;
the Retirement Lease digest was
`sha256:849f95e9104a4f2982ffd8fdb7ed1326518e3ecf2735c2cbfc522cb87e891e4d`.
The gate executed one harmless public-safe sentinel with gate receipt
`sha256:c7b29ec4d4f1bb2dc2075dec2ecbda4486e297027eb440876ae86e5de5a74961`.

After a late Spark consumer was injected, cache-bypassed complete paging found
two of two consumers. The existing dbt consumer remained closed and validated;
the new consumer was open and `OPAQUE`. The same campaign reversed to `UNSAFE`
with `POLICY_CONSUMER_OPAQUE` and `RECONCILIATION_NEW_CONSUMER`. The unsafe
manifest digest was
`sha256:8ebd40d18d8ae14ab71d7b2bd0463f8a1571c63541091dca27b05eeb1ffe2b33`.
The revoked summary was published and verified on first read-back. The agent
prepared no second Retirement Lease and did not call the gate again.

The public bundle is `artifacts/public/agent/full-run.json` and
`examples/agent-run/`. The aggregate evidence digest is
`sha256:0c30d644f08245c7647ccc7513819cc489e443b17c64383794338933df2e01fe`.
It binds five ignored raw traces by digest, asserts the exact MCP tool order,
and records zero product-agent shell calls. The concrete examples include the
one-line dbt patch, Change Receipt, Retirement Lease, readiness reversal, and
public-safe stage responses.

What this proves: the product agent performs the complete bounded operational
loop, takes a real reviewable Git/dbt action after external authorization,
accepts native evidence, publishes/read-backs durable DataHub state, executes a
manifest-bound gate, and revokes readiness when fresh evidence changes.

What this does not prove: independent adoption, production warehouse deletion,
universal discovery, a second automated native adapter, or safety beyond the
recorded evidence envelope.

## Post-goal semantic planner and GitHub PR evidence

Tested workstream commit: `88ade9052a5684113e017094951c8ed4737466ff`

Mode: live Vertex AI model proposal over bounded real DataHub and dbt context,
followed by deterministic plan freezing and a disposable public GitHub PR.

Observed result: `gemini-3-flash-preview` called
`read_datahub_context`, then `read_dbt_context`, then submitted one typed
proposal. Deterministic validation accepted `type_compatibility` and
`exact_model_output_parity`; a foreign-authority probe refused. The model
authorized nothing, accepted no validator result, and decided no readiness.

After external approval, the boundary changed exactly
`models/orders_model_00.sql` and one deterministic generated dbt test. Public
[acceptance PR #1](https://github.com/Arshgill01/retirement-conductor-semantic-pr-acceptance/pull/1)
remains open at head `6c26af7c11d36a6d1cc55cba38701982c1e546e3`.
The `semantic-dbt` check succeeded on that exact head with dbt Core 1.12.0 and
dbt-duckdb 1.10.1. A later owner commit invalidated the first receipt and was
preserved; recovery used a new bound receipt rather than overwrite.

The public aggregate is
`artifacts/public/semantic-pr/acceptance-summary.json`, with acceptance digest
`sha256:8610d08f8e928248870d490576e0bf1c9ea96428c683ba934e52873385f72ace`.
Its model evidence digest is
`sha256:037381ff857590c73d24849ed45953fdc45e942e285652962505703f5ce3367d`
and CI binding digest is
`sha256:78cd088f80fd1ee3725418392448a813a6605ae0a46872c6e7efc0db890fcbb0`.

What this proves: an actual LLM can select migration-specific safe validation
primitives and hand a typed proposal to deterministic authority; the resulting
reviewable diff, native dbt validation, PR, and CI head form one exact chain.

What this does not prove: model determinism, production GitHub policy,
independent adoption, glossary or field-quality coverage, or model authority.
Empty query history remained explicitly non-authoritative.

## Post-goal continuous Retirement Lease evidence

Tested workstream commit: `80ae38154026025aaf562d396e09a549111f3006`

Mode: live-local disposable DataHub Core v1.6.0 and Git/dbt campaign with an
issued producer plan, plus deterministic interruption and fault tests.

Observed result: the watcher started from `READY_TO_RETIRE` and an `ISSUED`
lease, performed cache-bypassed reconciliation, and independently reread the
exact DataHub `upstreamLineage` field edge for a newly introduced Spark
consumer. The campaign became `UNSAFE`, the DataHub summary was published and
read back, and the lease became `INVALIDATED`. The exact preserved old plan
then refused as `GATE_DECISION_NOT_READY`; no second producer sentinel was
written. Removing the late graph edge did not validate or close that consumer.

The public index is `artifacts/public/ws03/index.json`, with aggregate digest
`sha256:09b66f9c715d7867ffdadf75c54936a5eb844e42fdc71355d51329ef37a3a5bb`.
The watch receipt is `artifacts/public/ws03/watch-receipt.json`, digest
`sha256:56db58f8c08c547558e0bb032da7ee76b5a03c22bd4ecc41202ab30b254039e7`.

What this proves: readiness is observable and revocable after lease issue; the
late consumer is not merely a prearranged policy input, and the exact stale
authorization is demonstrably unusable. Observation, publication, and
verification resume from retained local authority after interruption.

What this does not prove: a distributed scheduler, production ingestion
latency, a real warehouse deletion, or safety beyond the recorded envelope.

## Post-goal Superset native-executor feasibility evidence

Tested workstream commit: `84e67079d6dd9d9e4ab79ffd274103a044495ba6`

Mode: live-local disposable Apache Superset 6.0.0, PostgreSQL, and DataHub Core
with the official DataHub 1.6.0 Superset connector.

Observed result: the executor bound exact dataset, database, and chart UUIDs,
required dataset ID 1 in the explicit allowlist, changed one virtual-dataset
SQL target through the native API, forced six-row chart execution, and matched
the safe semantic output digest. Fresh reingestion and direct reread observed
the replacement field edge without a legacy edge. Exact compensation restored
the before fingerprint and revalidated the chart. Missing approval, source
drift, connector failure, and an intervening owner change refused without
overwriting source state.

The inspected public summary is
`artifacts/public/superset/ws04-evidence.json`. It binds plan
`sha256:ccac87ec817d055160cb15fe74dcc452f33db522f193addaded7bf2f87eae208`,
validation
`sha256:df537c96111e3f954abc38be475d594ce818ca48dc49af9014c1954e3d443624`,
reconciliation
`sha256:311441d0f95b6e53ff0f61c2a58a24e63969ee424812a8fa8cc4e5f991a44917`,
and compensation
`sha256:c31b9ce1d7f93c2647f085248e7b04f1865e0ed7271a6fae5896601210873878`.

What this proves: a second native system can satisfy bounded identity,
authorization, mutation, validation, fresh metadata, and compensation
properties in a disposable environment.

What this does not prove: a supported second campaign adapter. The official
connector contract remains table-level; parser-derived field lineage is only
corroboration, and Superset receipts cannot affect canonical readiness or the
producer gate.

## Post-goal integrated workstream and packaged-agent acceptance

Integrated behavior commits: `b027c583fb3e55638e79eedab5ac350adcb58d20` and
`0db89e2260c0d1881a015cd18b18a09612185ea0`; packaged-agent acceptance commit:
`4c1d3976d1efffb99c4c0ae92f979351e3dd2599`.

Commands:

```text
make test-winning-workstreams
make check
make test-install
make test-upgrade
make test-reference-campaign
uv run python .agents/skills/retirement-conductor-agent/scripts/quick_validate.py .agents/skills/retirement-conductor-agent
```

Observed result: the integrated tree passed 55 focused winning-workstream
tests and 242 total tests, Ruff, formatting, strict mypy over 88 source files,
repository/link validation, secret and public-artifact review, reproducible
wheel/source builds, and whitespace validation. Four clean base installs,
upgrade/rollback, copied-state refusal, confirmed removal, and the installed
live-local reference passed. The installed reference executed 34 product CLI
operations from release 0.2.0, reached `READY_TO_RETIRE`, wrote one harmless
sentinel, then produced late and rich `UNSAFE` decisions with no source-checkout
CLI operation. Its evidence digest is
`sha256:26a675e9558840b946863eaa3c63ab3079c2b298660b1e61420b29c3c07563ca`.

The install test also installed `retirement-conductor[agent]` into a separate
clean Python 3.13 environment, opened an MCP client against the installed
server object, and listed exactly 16 tools including lease inspection and
fresh one-shot lease reconciliation. The install evidence digest is
`sha256:ec9136807e20521b03295e0188b27d51241824eabb9c7fd0fea5e98bff2e9e53`.
The project skill validator passed against the packaged 16-tool workflow.

Integration inspection found and corrected two issues before acceptance. The
Superset SQL replacement boundary now ignores comments, literals, and quoted
identifiers instead of rewriting token-shaped text outside executable
unquoted SQL. The installed-reference harness now identifies a reused healthy
DataHub Core container by its exact loopback published port before validating
image, state, and health, rather than depending on another worktree's Compose
environment file.

What this proves: the four workstreams coexist in one releasable tree; the
headline MCP interface survives packaging; continuous revocation is callable
through that interface; and the canonical installed reference still exercises
the full safe readiness/reversal loop after integration.

What this does not prove: that the semantic model proposal has been invoked in
the same recorded Codex run as the canonical 16-tool campaign, independent
operator adoption, production infrastructure, or a supported Superset
campaign adapter. The public narrated submission video and Devpost packaging
remain presentation work, not engineering evidence.

## Post-goal truth-experiment integration evidence

Audited integration base: `90872dc03c0fc900d39fd35e3c32778e5b0973ae`.
The frozen experiment inputs and final public artifacts were committed in that
order on the merged histories. TE-04 independently verified all three public
self-digests, the TE-02 frozen corpus and oracle, aggregate counts, retained
failures, and the merged focused test surface before selecting architecture.

TE-01 mode: 15-scenario deterministic fixture truth with 135 final attempts,
including 90 live Vertex AI attempts and 180 unique native response IDs. The
frozen corpus commit is `4c171ce`; tested behavior is `86b1524`. The canonical
summary digest is
`sha256:14e4c48066fcc62bd50c2d35a26642a3f6f91c59cae5ac371c7215eac5f6c359`.
Full DataHub context improved critical fault coverage from 53.3% to 100%, but
the nested Gemini arm achieved 20% exact minimum plans and accepted 48
unnecessary checks. Recommendation: remove nested Gemini and keep bounded
DataHub context. Raw request/response evidence remains ignored and private.

TE-02 mode: deterministic fixture truth through durable campaign state,
live-local DataHub Core, and disposable native Git/dbt. The frozen truth commit
is `f10a7e3`; tested behavior is `b88affc`; the public evidence digest is
`sha256:28e8cfc536700232533b92ec67a18a72041be2e8d231a8f59f985fce74fe0220`.
All 24 cases matched the independent oracle, recalled 121/121 controlled
consumers, produced zero false readiness and one producer action, and refused
unchanged-watch, late-consumer, and expired lease sequences as declared.
Non-applicability receipts remain controlled fixture evidence, not native
validation or model authority.

TE-03 mode: 72 Codex runs over deterministic disposable campaign state with
live-local DataHub MCP availability. The frozen corpus commit is `af82d88`;
the launcher-repair commit is `a451758`; final public evidence is `4d68383`.
The aggregate digest is
`sha256:c7a747618debc99e9f45d6d27cba80823ee9e88151c894068bb23f340652fb32`.
The skill raised correct completion from 66.67% to 95.83%, and MCP-only reached
66.67% versus 29.17% for CLI/shell. All 26 scored failures and 24 pre-model
host failures remain digest-bound. Every formal run had
`capability_bounded=false`; shell and file editing were present in every arm
and DataHub advertised metadata mutation tools.

Spot-check commands and results:

```text
uv run python <offline canonical digest and aggregate assertion>
Result: TE_INPUT_EVIDENCE_SPOTCHECK_PASSED

uv run python -m scripts.run_retirement_gauntlet_v2 --verify-frozen-only
Result: FROZEN_TRUTH_VERIFIED; 24 cases

uv run pytest -q tests/unit/test_semantic_ablation.py tests/unit/test_semantic_model_planner.py tests/unit/test_semantic_validation.py tests/unit/test_retirement_gauntlet_v2.py tests/integration/test_campaign_store.py tests/unit/test_agent_boundary_ablation.py tests/unit/test_agent_mcp.py
Result: 56 passed
```

What this proves: the integrated artifacts preserve their audited inputs,
digests, aggregate outcomes, failures, and predeclared recommendations. The
evidence selects removal of nested Gemini, retention of bounded DataHub
context, retention of the project skill and product MCP, and retention of the
durable campaign/lease boundary.

What this does not prove: production graph coverage, customer value,
independent operation, universal model behavior, or capability-bounded host
execution. Those non-claims govern the definitive TE-04 run.

## TE-04 definitive unified agent evidence

Behavior commit: `2635240b611f9e18a1e9e4e96541c871a786dc88`.
Initial public evidence commit: `6eeea35`. The integration audit corrected a
version-label defect that had identified the Git/dbt adapter version as the
Retirement Conductor package version; the run used Retirement Conductor 0.2.0
with Git/dbt adapter 0.1.0. Evidence mode: one persistent Codex task
over disposable live-local DataHub Core 1.6.0, a disposable Git/dbt checkout,
and a real public GitHub PR/Actions boundary. The public index is
[`artifacts/public/definitive-unified-run/index.json`](../artifacts/public/definitive-unified-run/index.json)
with digest
`sha256:35dc492254c1fd196c51c743455d71c065b1245694867f697ae94f2de61143e9`.

Host: Codex CLI 0.147.0, `gpt-5.4`, medium reasoning,
`workspace-write`, approvals `never`, the retained project skill, DataHub MCP,
and the 16-tool Retirement Conductor MCP. DataHub advertised 20 tools,
including metadata mutations. Shell and file editing remained callable. The
agent made four expected read-only shell calls to load the skill, its reference,
the campaign, and working directory; it made zero unexpected shell calls, zero
unrelated MCP calls, zero direct file edits, and zero producer-gate calls. This
is not capability-bounded evidence.

Observed bindings:

- plan `sha256:c4241b03be165e83894e41807e3b0cd4ee8157204ac2106453215a907e960f29`
  authorized exactly `models/orders_isolated_model.sql`;
- user-directed external approval
  `sha256:40023cc35eb68873c23f7d059c7f323352b49bd8fdf4576085fe305e2dfaefc1`;
- native commit `32984004f80d8be0884f72f7767d86fa97b93bec` and validation
  receipt `sha256:b2585fe2ed1a39be089563e2cf390f7fb02ea2029fc40beecdeaea8d30740f42`;
- public [PR #1](https://github.com/Arshgill01/retirement-conductor-definitive-acceptance/pull/1)
  reread the same head and one-file scope; the named
  [`semantic-dbt` job](https://github.com/Arshgill01/retirement-conductor-definitive-acceptance/actions/runs/31325110949/job/93274114385)
  passed;
- reconciliation became `READY_TO_RETIRE` at comparison digest
  `sha256:c932d4ff339c4106754a3b7d2576a2a53e4c2d7db4a3b5dde64d50ce43493777`;
- DataHub publication URN
  `urn:li:document:shared-93113e95-a262-45ac-9cf2-b1163e31b6b1` read back the
  published manifest, and a fresh DataHub-only agent found it while preserving
  bounded language;
- lease `sha256:1600d6dcfa6ee9416870265b46a1fea3bcca4ee87d53d8137b82cc0016a910e2`
  was `ISSUED`; a new exact-field consumer then produced watch receipt
  `sha256:1fee3a8c2e46d38a391c99b92a5c6e3a6f85c1b361ff3860dc42fa459c2cded6`,
  changed the decision to `UNSAFE`, and projected the lease as `INVALIDATED`;
- the preserved producer gate refused with `GATE_DECISION_NOT_READY`; zero
  sentinels and zero producer actions existed.

The raw six-stage primary trace and fresh-agent trace remain ignored local
evidence because they contain machine-specific paths. Their SHA-256 digests,
exact prompts, observed call order, redaction classification, model/host
configuration, and full advertised tool inventory are in the public index.
The offline verifier recomputes the public self-digest and asserts the PR/CI,
publication, lease-reversal, gate-refusal, non-capability, and zero-action
invariants without network or paid model calls.

Final acceptance inspected on the evidence-promoted tree:

```text
uv run python -m scripts.run_retirement_gauntlet_v2 --verify-frozen-only
Result: FROZEN_TRUTH_VERIFIED; 24 cases

uv run pytest -q tests/unit/test_retirement_gauntlet_v2.py tests/integration/test_campaign_store.py tests/integration/test_watch.py
Result: 37 passed

make test-install
Result: reproducible package; four clean runtimes; installed agent exposed 16 MCP tools; removal passed

make test-ui
Result: 16 tests passed; both UI artifacts passed deterministic accessibility review

make check
Result: 256 tests; Ruff; formatting; strict mypy over 92 source files; 204-file repository and 165-link validation; 407-file secret review; 83-file public-artifact review; source/wheel build; diff check passed
```

What this proves: the architecture selected by TE-01 through TE-03 completed
one bounded real-agent campaign with exact native validation, public PR/CI,
shared DataHub memory, and post-lease reversal. It also exposed and repaired
the unsafe division of clock responsibility: agent-facing authorization and
lease windows now come from the trusted runtime.

What this does not prove: production graph coverage, independent operator or
customer value, universal model behavior, authorship from digests, or host
capability containment. The author and external authorization operator were
the same evaluator; DataHub and the harmless producer boundary were disposable
local services.

## Post-goal Retirement Workbench evidence

Behavior commit: `17ec47f77599e0471ee1f3edf7bb0be01ad44168`.
Evidence mode: the Workbench read the retained 18-event author-operated
live-local agent campaign through a loopback API with actions disabled. The
same route was then inspected at 1600 × 1000 and 390 × 844, and without the API
to exercise its explicitly recorded public fallback.

Observed bindings:

- every Workbench read verified the canonical manifest and required the exact
  event-digest sequence to equal manifest transition history;
- the displayed `UNSAFE` state, added consumer ID, accepted Git/dbt receipt,
  DataHub evidence coverage, publication read-back, and invalidated lease came
  from those records; the view did not infer the late consumer's platform;
- the API accepted only `127.0.0.1` and loopback browser origins, disabled
  runtime actions by default, and rejected operations outside inventory and
  reconciliation;
- first-tab skip navigation reached the campaign content, visible focus and
  native controls remained available, reduced-motion mode rendered normally,
  and the 390-pixel layout had no page-level horizontal overflow;
- the committed site preview screenshots are indexed in
  [`artifacts/public/workbench/README.md`](../artifacts/public/workbench/README.md);
- the recorded projection SHA-256 is
  `c702bd127679965537cb821474c53900afaf2ba71aa43b882e59d718acdd0af9`
  and it retains canonical manifest digest
  `sha256:49aa07fa4afd1e065c0eedfbaaa7074be0827a9917e9941047183ba49a7efe28`.

Acceptance on the behavior tree:

```text
make check
Result: 262 tests passed; Ruff; formatting; strict mypy; repository/link,
secret, and public-artifact checks; source/wheel builds; diff check passed

npm --prefix site run lint
Result: passed

npm --prefix site test
Result: production build and 5 rendered-route tests passed
```

What this proves: one polished operator route renders and navigates real
canonical campaign evidence without adding browser policy authority, and the
two opt-in runtime operations preserve the existing command boundary.

What this does not prove: production graph coverage, a shared multi-operator
service, independent adoption, or safe browser authorization/apply/gate
controls. Those mutation boundaries remain intentionally absent.

## Post-goal lease-value, operator, and heterogeneous-campaign evidence

Behavior and public-evidence commit: `87bbf41`. Evidence modes: paired analysis
over inspected live-local evidence, prepared-not-run human evaluation, and a
new live-local DataHub Core 1.6.0 plus Git/dbt plus Superset 6.0.0 campaign.

The frozen lease-value protocol is
[`fixtures/lease-value-comparison-v1/FROZEN.json`](../fixtures/lease-value-comparison-v1/FROZEN.json).
Its executable static arm persisted the same pre-intervention
`READY_TO_RETIRE` decision and intentionally had no refresh or revocation
operation. Under the inspected WS-03 late exact-field intervention it therefore
retained stale green. The Retirement Lease arm changed to `UNSAFE`, became
`INVALIDATED`, refused the preserved plan with `GATE_DECISION_NOT_READY`, and
changed the producer sentinel count by zero. Public report digest:
`sha256:267ad05d9971785b27e430ca8e002ae9473bf68c3edd7d28b0ec0dc7c30e1dcd`.
The static arm is a minimal contract, not a named-vendor comparison.

The independent-operator packet generator built a checksum-bound wheel, source
archive, runbooks, participant brief, and observation template under ignored
runtime state. It explicitly emits `PREPARED_NOT_RUN`, records every author
intervention as disqualifying evidence, and offers a 30–45 minute bounded
core-workflow observation plus a 60–90 minute full RC-018 track. No person had
completed the packet when this entry was written; RC-018 remains `NOT_RUN`, and
no adoption, willingness, frequency, or buyer claim is made.

The heterogeneous acceptance used one exact PostgreSQL producer field in
DataHub, a public-safe seeded dbt field edge, and the official DataHub 1.6.0
Superset connector. Two connector runs each exited zero, reported eight records,
and were followed by direct stored-aspect rereads rather than trusted as closure
evidence. Git/dbt applied one exact model change and passed parse, seed, build,
and test in the bubblewrap/DuckDB boundary. Superset applied one exact
allowlisted virtual-dataset change, retained dataset/database/chart UUIDs, and
passed forced saved-chart semantic parity. The canonical campaign accepted both
live receipts, recorded two exact native migrations, and became
`READY_TO_RETIRE`. Authorized Superset compensation made that consumer `STALE`
and the campaign `UNSAFE`. Public evidence digest:
`sha256:e043a644780542acc46ff6d99523729a645406927225fe55270a06e85f45b03d`.

Commands and inspected results:

```text
make lease-value-comparison
Result: REVOCABLE_LEASE_ADDS_DECISIVE_SAFETY_VALUE

make heterogeneous-datahub
Result: exact public-safe dbt field edge written and digest-bound

uv run python scripts/run_heterogeneous_campaign_acceptance.py
Result: HETEROGENEOUS_CAMPAIGN_PASSED

make check
Result: 261 tests; Ruff; formatting; strict mypy over 97 source files;
204-file repository and 175-link validation; 426-file secret review;
90-file public-artifact review; source/wheel build; diff check passed
```

What this proves: revocation adds an observable safety property beyond static
impact sign-off; Superset can now participate consequentially in the same
campaign, receipt, reconciliation, and readiness kernel as Git/dbt; and the
remaining independent-human boundary is executable without being fabricated.

What this does not prove: production coverage, broad customer demand,
independent operability, or a second complete producer-gated executor. The
final gate still independently refreshes only DataHub and Git/dbt, so Superset
remains campaign-integrated experimental scope.

## Finalized hosted Retirement Workbench evidence

Behavior commits: `d9d366f` and `68c2139`. Site source commit:
`1f2ecb61414f0e354c69eaa2ec27b1018a27ce44`. Evidence mode:
author-operated public HTTPS page paired to a loopback runtime over the retained
18-event campaign, with actions disabled.

Observed bindings and refusals:

- the public page loaded labeled recorded evidence without probing loopback;
- pairing required the exact configured HTTPS origin and a fresh process token;
- missing and incorrect tokens returned HTTP 401, insecure remote origins and
  non-loopback binds refused, and private-network preflight did not widen the
  allowlist;
- normal Chrome displayed its Local Network Access prompt; only after an
  explicit **Allow** did authenticated health and view reads complete;
- health and view returned the same campaign ID, after which the visible mode
  changed to `PAIRED READ ONLY` and the Evidence view remained navigable;
- SQLite access is serialized across reads and operations; injected contention
  returns stable `RUNTIME_STORE_LOCKED` instead of leaking a traceback;
- rejected visual prototypes and the query-parameter variant surface were
  removed from the production tree.

Acceptance results:

```text
TMPDIR=/home/arshdeepsingh/.rc-check-workbench make check
Result: 271 tests; Ruff; formatting; strict mypy over 100 source files;
204-file repository and 179-link validation; 437-file secret review;
92-file public-artifact review; source/wheel build; diff check passed

npm --prefix site run lint
Result: passed

npm --prefix site test
Result: production build and 6 rendered-route tests passed

Sites production deployment
Result: version 4 succeeded at
https://retirement-conductor.arshgill01.chatgpt.site/workbench
```

The public pairing record is
[`artifacts/public/workbench/pairing-acceptance.json`](../artifacts/public/workbench/pairing-acceptance.json),
SHA-256
`f368ddd4342ea236dcb861a91396592021b77e14acec8740137ca6a2a826cdf6`.

What this proves: the accepted public design can become a real canonical
single-campaign operator view through an explicitly authorized, token-bound
loopback companion without moving DataHub credentials or policy authority into
the hosted application.

What this does not prove: production graph coverage, shared multi-operator
operation, independent adoption, or browser authority over authorization,
apply, receipt acceptance, lease issuance, or producer execution. The final
acceptance was intentionally read-only and did not invoke inventory or
reconciliation.
