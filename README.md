# Retirement Conductor

Retirement Conductor safely replaces and retires legacy data fields by finding
known consumers across systems, changing the consumers it is authorized to
change, validating each change with the consumer's own tools, and refusing the
producer-side retirement action until the evidence closes.

The public [technical dossier](https://retirement-conductor.arshgill01.chatgpt.site)
explains the complete product, evidence, safety boundary, official and
synthetic data benchmark, limitations, and copyable end-to-end verification
commands. Its standalone source is tracked under [`site/`](site/).

## The agent demo

Retirement Conductor now exposes the same campaign engine as a project-scoped
MCP server with a Codex skill. The model can discover context, inspect state,
plan the exact Git/dbt change, invoke native validation, reconcile fresh
evidence, and explain a decision. It cannot authorize its own plan, and it
cannot override the deterministic producer gate.

The highest-signal demo starts with a campaign that was ready after one dbt
consumer was migrated and validated. Fresh DataHub reconciliation then finds a
late Spark consumer. Codex calls the MCP inspection tools, explains why the
same campaign is now `UNSAFE`, and refuses to invoke retirement. Run the
model-driven retained-state acceptance trace with:

```bash
make agent-acceptance
```

See [the agent demo runbook](docs/runbooks/AGENT_DEMO.md) for the complete live
path, exact human-authorization pause, adversarial prompts, and judge script.
The audit behind this path also produced upstream DataHub MCP
[PR #195](https://github.com/acryldata/mcp-server-datahub/pull/195) for correct
lineage pagination and
[PR #196](https://github.com/acryldata/mcp-server-datahub/pull/196) for accurate
deployment-gate diagnostics.

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
queries, metadata mutation, and an agent-readable context surface. Git and dbt
know how to change and validate the supported repository consumer. Retirement
Conductor owns the part between them:

- one durable campaign across unrelated consumer systems;
- a common adapter and evidence contract;
- source-version and scope preconditions before mutation;
- per-consumer native validation receipts;
- a fresh reconciliation pass that can reopen the campaign;
- a deterministic producer-side gate;
- an auditable explanation of what is closed, unknown, stale, or unsafe.

The system does not replace DataHub, dbt, Git, or their validators. It makes
them participate in one completion criterion while keeping non-repository
DataHub consumers visibly opaque until independent evidence closes them.

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

The former deterministic Looker experiment did not receive live evidence and
is no longer part of the supported product or completion contract. Its
historical fixture results remain labeled in the evidence ledger; the active
work replaces that dependency with an evidence-quality benchmark over
official DataHub hackathon datasets and deterministic synthetic truth sets.
See [the current goal](GOAL.md).

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

Phase 06 now stress-tests that same engine over four checksum-pinned official
DataHub datasets and deterministic synthetic truth. A live-local Core run
directly reread schema, field lineage, owner, domain, tag, glossary, and
quality aspects; the independent oracle matched all 14 scenarios with zero
false readiness. The clean isolated campaign reached `READY_TO_RETIRE`, while
partial, stale, ambiguous, table-only, incompatible, null-inflated,
semantic-drift, late, and opaque-rich cases stayed blocked or unsafe. Three
full runs share one time-independent semantic digest. See
[EP-006](docs/EVIDENCE_LEDGER.md#phase-06-post-removal-confirmation).

The refreshed Phase 07 boundary separates plan from apply, refuses copied
campaign stores, verifies online backup and original-path restore, exposes redacted
operational diagnostics, and audits dependencies, licenses, secrets, and
public artifacts. After removal, the focused security, fault, and recovery
suites passed 53, 47, and 40 tests. The all-group audit found no known
vulnerability in 18 installed packages, plan-only Git/dbt remained unable to
apply, backup/restore reproduced the manifest, and copied state refused before
database change. See
[the Phase 07 observations](docs/EVIDENCE_LEDGER.md#phase-07-post-removal-acceptance).

The 0.2.0 release boundary then reproduced its wheel and source archive,
installed cleanly under Python 3.11 through 3.14, preserved one campaign
through upgrade and backup-based rollback, and removed only explicitly
confirmed state. A clean installed wheel—not the source checkout—executed the
complete live-local Core/Git/dbt reference: one ready sentinel, late-consumer
reopening, and rich-graph refusal. The independent-operator artifact remains
`NOT_RUN`, so this is engineering and integration evidence, not customer-value
evidence.

## Complete supported path

The first production-shaped vertical is:

- one warehouse column and one compatible replacement;
- DataHub as the cross-system inventory and reconciliation surface;
- one Git repository containing dbt or SQL consumers;
- reviewable branch-based changes;
- dbt-native validation;
- a durable local campaign record plus a DataHub summary;
- a command that exits non-zero when producer retirement is not permitted.

Git/dbt is the sole automated native mutation boundary. Other DataHub-observed
asset types remain blockers or externally receipted consumers; additional
native adapters are explicitly outside the current build boundary.

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
- [Deployment runbook](docs/runbooks/DEPLOYMENT.md)
- [Recovery runbook](docs/runbooks/RECOVERY.md)
- [Compatibility matrix](docs/COMPATIBILITY.md)
- [Independent evaluation](docs/EVALUATION.md)
- [Maintenance policy](docs/MAINTENANCE.md)
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
The official-dataset and synthetic evidence-quality benchmark is controlled by
[the current goal](GOAL.md) and
[Phase 06](docs/phases/06-data-quality-benchmark.md); its executable boundary
is documented in the
[benchmark runbook](docs/runbooks/DATA_QUALITY_BENCHMARK.md).
Threat boundaries, least-privilege capabilities, retention, failure handling,
verified backup and restore, diagnostics, and recovery drills are documented
in the [security model](docs/SECURITY_MODEL.md), [security policy](SECURITY.md),
and [recovery runbook](docs/runbooks/RECOVERY.md).

The supported one-host, single-writer wheel installation, secret-reference
configuration, preflights, local opt-in diagnostics, upgrade, rollback,
confirmed state removal, and package uninstall are documented in
[the deployment runbook](docs/runbooks/DEPLOYMENT.md). Executed and unverified
platform boundaries are separated in
[the compatibility matrix](docs/COMPATIBILITY.md). A real prospective
operator must follow [the independent evaluation guide](docs/EVALUATION.md);
the built-in fixture and author-run reference cannot substitute for that
adoption evidence. Release compatibility and evidence maintenance follow
[the maintenance policy](docs/MAINTENANCE.md).

See [CONTRIBUTING.md](CONTRIBUTING.md) before changing a product contract or
phase boundary.
