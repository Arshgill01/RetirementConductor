# Retirement Conductor

Retirement Conductor safely replaces and retires legacy data fields by finding
known consumers across systems, changing the consumers it is authorized to
change, validating each change with the consumer's own tools, and refusing the
producer-side retirement action until the evidence closes.

## The problem in plain language

An old warehouse column can look unused in its repository while still feeding
a dashboard, scheduled report, notebook, pipeline, or model elsewhere. A
catalog can reveal much of that blast radius, but a list of affected assets
does not move those consumers or prove that they still work after a change.

Retirement Conductor turns the change into one controlled campaign:

```text
Declare what is being replaced
  → build an evidence-scoped consumer inventory
  → migrate authorized consumers
  → run source-native validation
  → discover again from fresh state
  → permit or refuse retirement
```

Its central promise is deliberately bounded:

> Never confuse “nothing was returned” with “nothing depends on it.”

## Why this is a product rather than one catalog feature

DataHub supplies cross-system lineage, ownership, schemas, usage context,
queries, metadata mutation, and an agent-readable context surface. Native
platform tools know how to change and validate their own objects. Retirement
Conductor owns the part between them:

- one durable campaign across unrelated consumer systems;
- a common adapter and evidence contract;
- source-version and scope preconditions before mutation;
- per-consumer native validation receipts;
- a fresh reconciliation pass that can reopen the campaign;
- a deterministic producer-side gate;
- an auditable explanation of what is closed, unknown, stale, or unsafe.

The system does not replace DataHub, dbt, Looker, Git, or their validators. It
makes them participate in one completion criterion.

## Evidence already established

The preceding experiment exercised a live DataHub Core graph and a real
disposable dbt project:

- repository analysis found one consumer;
- DataHub expanded the inventory to 35 consumers across multiple platforms;
- DataHub therefore changed the decision from allowed to refused;
- the repository consumer was protected by a content hash, changed, parsed,
  built, and tested;
- stale source and invalid replacement cases refused safely;
- unresolved external consumers remained blocking;
- a stable refusal summary was written to DataHub and read back through its
  agent surface.

A second adapter has deterministic contract coverage for one bounded Looker
saved-content mutation, rollback, validation, recreated-identity handling,
unknown-outcome recovery, and fresh legacy/replacement edge reconciliation.
Its live boundary remains unverified until a disposable instance and scoped
credentials are available. See
[Evidence baseline](docs/EVIDENCE_BASELINE.md).

This repository has now independently exercised its phase 02 product path
against a fresh disposable DataHub Core v1.6.0 instance. It resolved the exact
field pair, retrieved all 31 advertised graph consumers over seven pages, and
found at least 30 more consumers than the one configured repository reference.
It updated one stable campaign document four times, read the exact content
back, and verified that the target lifecycle remained unchanged. The result
was deliberately `UNSAFE`: all graph consumers remain opaque until their
native systems close them. See
[EP-002](docs/EVIDENCE_LEDGER.md#ep-002--phase-02-datahub-evidence-boundary).

Phase 03 then joined one of those fresh graph identities to one exact dbt
manifest node and file. Two separately approved review branches each changed
only that file; native dbt parse, seed, build, and test passed; Git rollback
restored and revalidated the source; reapply produced one accepted live
receipt. Stale, overbroad, incompatible, and hostile cases refused or remained
inside the disposable validator boundary. The campaign still ended `UNSAFE`
because 30 consumers remain opaque and reconciliation has not run. See
[EP-003](docs/EVIDENCE_LEDGER.md#ep-003--phase-03-git-and-dbt-execution).

Phase 04 completed that first vertical in two live disposable campaigns. An
isolated one-consumer campaign reconciled equivalent fresh scope, published
and verified its final DataHub summary, and executed one short-lived
manifest-bound producer sentinel. Replay, drift, tampering, unavailable state,
and untrusted provenance all refused. Adding a second consumer reopened the
same campaign to `UNSAFE`, while the representative 31-consumer graph also
refused the producer action. See
[EP-004](docs/EVIDENCE_LEDGER.md#ep-004--phase-04-reconciliation-and-producer-gate).

Phase 05 now renders that same canonical state through plain-language
`inspect` and `explain` commands plus deterministic single-campaign HTML.
The evidence covers all four final decisions, exact plan-digest confirmation,
structurally redacted public export, desktop and 360-pixel mobile browser
flows, 15 keyboard-reachable controls, and two axe-core audits with zero
violations or incomplete results. The positive-looking all-closed fixture
remains visibly `BLOCKED` because fixture evidence cannot satisfy live policy.
See
[EP-005](docs/EVIDENCE_LEDGER.md#ep-005--phase-05-operator-experience).

The credential-independent Phase 07 boundary now separates plan from apply,
classifies ambiguous mutations without blind retry, refuses copied campaign
stores, verifies online backup and original-path restore, exposes redacted
operational diagnostics, and audits dependencies, licenses, secrets, and
public artifacts. The focused security, fault, and recovery suites passed 93,
72, and 43 tests, and the all-group audit found no known vulnerability in 18
installed packages after upgrading the one vulnerable development dependency.
These fixture and analysis results do not complete Phase 07: live
Looker-specific permission and failure behavior remains coupled to `EP-006`.
See
[the Phase 07 observations](docs/EVIDENCE_LEDGER.md#phase-07-credential-independent-observations).

## Complete supported path

The first production-shaped vertical is:

- one warehouse column and one compatible replacement;
- DataHub as the cross-system inventory and reconciliation surface;
- one Git repository containing dbt or SQL consumers;
- reviewable branch-based changes;
- dbt-native validation;
- a durable local campaign record plus a DataHub summary;
- a command that exits non-zero when producer retirement is not permitted.

Looker is the next native adapter after this path works completely. Other asset
types and platforms are explicitly outside the current build boundary.

## Product rules

```text
The model proposes.
Native tools validate.
Deterministic policy decides.
```

- `READY_TO_RETIRE` means ready within a declared evidence envelope, never
  universally safe.
- Missing required evidence is `BLOCKED`.
- A known active or failed consumer is `UNSAFE`.
- Semantic or ownership judgment that cannot be automated is
  `REVIEW_REQUIRED`.
- A new consumer or stale receipt reopens the campaign.

## Repository map

- [Autonomous implementation contract](GOAL.md)
- [Current execution state](STATUS.md)
- [Product definition](docs/PRODUCT.md)
- [Build plan](PLAN.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Core contracts](docs/CONTRACTS.md)
- [Requirements traceability](docs/REQUIREMENTS_TRACEABILITY.md)
- [Evidence ledger](docs/EVIDENCE_LEDGER.md)
- [Access requirements](docs/ACCESS.md)
- [Security model](docs/SECURITY_MODEL.md)
- [Recovery runbook](docs/runbooks/RECOVERY.md)
- [Risk register](docs/RISKS.md)
- [Decision log](docs/DECISIONS.md)
- [Phase index](docs/phases/README.md)
- [Research passes](docs/research/README.md)
- [Agent operating rules](AGENTS.md)

## Working in this repository

This repository contains the controlling product contracts and an executable
Python campaign engine with live DataHub and Git/dbt boundaries, versioned
schemas, deterministic fixtures, and stable refusal behavior. The continuous
implementation run is governed by [GOAL.md](GOAL.md); its active phase and
honest external boundaries live in [STATUS.md](STATUS.md).

Create the pinned development environment and run the repository checks with:

```bash
uv sync --all-groups
make check
```

The phase 00 commands are:

```bash
retirement-conductor validate-spec fixtures/specs/valid.yaml
retirement-conductor fixture run fixtures/specs/valid.yaml
```

The deterministic campaign kernel can replay and evaluate the tracked blocked
fixture:

```bash
retirement-conductor campaign replay fixtures/campaigns/blocked
retirement-conductor campaign evaluate fixtures/campaigns/blocked
```

The disposable live DataHub workflow and its no-secret configuration are
documented in [the DataHub Core runbook](docs/runbooks/DATAHUB_CORE.md).
The bounded repository mutation and native validation sequence is documented
in [the Git/dbt runbook](docs/runbooks/GIT_DBT.md).
Fresh reconciliation, stable publication, and the one-time producer gate are
documented in
[the reconciliation and gate runbook](docs/runbooks/RECONCILIATION_GATE.md).
Campaign inspection, exact plan confirmation, resume, local and public report
generation, and operator acceptance checks are documented in
[the operator runbook](docs/runbooks/OPERATOR.md).
The credential-independent Looker recipes, no-secret access packet, and
bounded live lifecycle are documented in
[the Looker runbook](docs/runbooks/LOOKER.md).
Threat boundaries, least-privilege capabilities, retention, failure handling,
verified backup and restore, diagnostics, and recovery drills are documented
in the [security model](docs/SECURITY_MODEL.md), [security policy](SECURITY.md),
and [recovery runbook](docs/runbooks/RECOVERY.md).

See [CONTRIBUTING.md](CONTRIBUTING.md) before changing a product contract or
phase boundary.
