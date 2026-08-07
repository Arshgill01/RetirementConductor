# Retirement Conductor: complete project and hackathon context

**Status snapshot:** 2026-08-07 (UTC)  
**Repository:** <https://github.com/Arshgill01/RetirementConductor>  
**Public technical dossier:** <https://retirement-conductor.arshgill01.chatgpt.site>  
**Hackathon:** [Build with DataHub: The Agent Hackathon](https://datahub.devpost.com/)  
**Submission deadline:** 2026-08-10 at 5:00 p.m. EDT / 21:00 UTC  
**Current conclusion:** the credential-independent engineering goal and a
judge-visible MCP agent path are implemented; the hackathon submission package
is not yet verifiably complete.

This document is the consolidated handoff for the project: product thesis,
hackathon context, current repository state, implementation, architecture,
evidence, phases, safety rules, release status, risks, limitations, submission
readiness, and next actions. It summarizes the controlling repository records;
those records remain authoritative when details conflict.

## 1. Executive summary

Retirement Conductor is a DataHub-native control plane for safely replacing
and retiring legacy data fields. It does more than show impact. It creates a
durable campaign, inventories known consumers through a bounded evidence
envelope, changes only an explicitly authorized Git/dbt consumer, validates
that change with dbt, inventories again, publishes the result to DataHub, and
refuses the producer-side retirement action unless deterministic policy says
the recorded evidence is sufficient.

The core rule is:

> Never interpret “nothing was returned” as “nothing depends on it.”

The implementation is deliberately narrow:

- one legacy warehouse column and one compatible replacement column;
- DataHub Core for cross-system context and reconciliation;
- one Git repository containing a dbt or SQL consumer;
- a reviewable branch or patch as the mutation boundary;
- dbt-native parsing, building, and semantic tests;
- local single-writer SQLite campaign state;
- a stable DataHub campaign summary;
- a one-time producer-side gate that exits non-zero unless the campaign is
  `READY_TO_RETIRE`.

Git/dbt is the only automated native mutation boundary. Dashboards, notebooks,
pipelines, models, and other non-repository consumers discovered through
DataHub remain visible blockers until an independent native receipt, verified
removal, or proved non-applicability closes them.

### Where the project stands

- The controlling engineering goal in `GOAL.md` is **complete**.
- Phases 00 through 08 are all marked complete for the credential-independent
  engineering boundary.
- RC-001 through RC-017 and RC-019 have direct acceptance evidence.
- RC-018, independent operation and customer-value evidence, is still
  **`NOT_RUN` / `NOT_SATISFIED`**.
- The current release is `retirement-conductor` **0.2.0**.
- The supported release contains DataHub plus Git/dbt boundaries only.
- The former Looker adapter was intentionally removed; it is historical,
  superseded evidence, not supported product behavior.
- Phase 06 matched **14/14** oracle scenarios with **zero false readiness**,
  **100% expected-consumer recall** in the controlled graph, one permitted
  sentinel action, and correct refusal of late and rich graphs.
- The repository is public and reports an Apache-2.0 license.
- Before the 2026-08-07 agent work began, local `main` was clean and exactly
  matched `origin/main` at
  `e12249145d088b1b6ef39fa4240d72fbe6aa51bf`. Branch
  `codex/agent-demo-and-datahub-contributions` now contains the MCP agent,
  Codex skill, acceptance runner, judge runbook, public agent evidence, and
  this context document in three focused commits. Its clean HEAD passed 190
  tests, Ruff, formatting, strict mypy, 191-file repository validation,
  secret and public-artifact scans, reproducible package builds, a 14-tool
  STDIO MCP handshake, skill validation, site build/tests/lint, and
  `git diff --check`.
- The deployed public dossier returned HTTP 200 on 2026-08-07.
- No demo-video URL or Devpost project/submission URL is tracked in the
  repository. Those assets may exist elsewhere, but they are **not verified**
  by this audit.

The immediate project risk is therefore not “does the software exist?” It is
“can the remaining submission materials make the working software obvious to
judges before the deadline?”

### 2026-08-07 agent and upstream update

- `retirement-conductor-mcp` exposes 14 focused tools over STDIO while calling
  the existing CLI dispatcher and deterministic policy in-process.
- The server intentionally exposes no authorization-recording tool. A human
  must review the exact plan and run the returned CLI authorization command
  outside the model.
- `.agents/skills/retirement-conductor-agent/` gives Codex the complete
  failure-closed sequence, including DataHub context, native validation,
  reconciliation, publication, and gate rules.
- `.codex/config.toml` registers both Retirement Conductor and the optional
  local DataHub MCP server at project scope.
- A real ephemeral Codex trace used exactly
  `inspect_retirement_campaign` and `explain_retirement_campaign`, made zero
  shell calls, found the late opaque consumer, and plainly refused retirement.
  `make agent-acceptance` makes this trace repeatable over retained live state.
- The audit opened DataHub MCP
  [issue #194](https://github.com/acryldata/mcp-server-datahub/issues/194) and
  [PR #195](https://github.com/acryldata/mcp-server-datahub/pull/195) for broken
  lineage offset pagination, plus
  [PR #196](https://github.com/acryldata/mcp-server-datahub/pull/196) for the
  existing deployment-gate logging issue #192. Both PRs are open; maintainer
  acceptance and CI remain external.

## 2. Source-of-truth order

When resuming work, read in this order:

1. `AGENTS.md` — operating, safety, scope, and evidence rules.
2. `GOAL.md` — controlling end-to-end engineering contract.
3. `STATUS.md` — current phase and boundary state.
4. `README.md` — public project explanation and workflow.
5. `docs/PRODUCT.md` — user, buyer, promise, and non-claims.
6. `PLAN.md` — proof order and complete vertical.
7. The relevant file under `docs/phases/`.
8. `docs/REQUIREMENTS_TRACEABILITY.md`.
9. Relevant sections of `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`,
   `docs/RISKS.md`, `docs/DECISIONS.md`, and `docs/EVIDENCE_LEDGER.md`.
10. `docs/research/` before changing positioning, DataHub boundaries,
    supported scope, or competitive claims.

`GOAL.md` controls the completed implementation run. `STATUS.md` records the
current truth. The evidence ledger, not an exit code or a prose claim, records
what was actually observed.

## 3. Hackathon context

External facts in this section were checked against the official Devpost
[overview](https://datahub.devpost.com/),
[rules](https://datahub.devpost.com/rules),
[dates](https://datahub.devpost.com/details/dates), and
[resources](https://datahub.devpost.com/resources) on 2026-08-07.

### 3.1 Schedule

| Milestone | Official time |
|---|---|
| Registration and submission period | 2026-07-06 09:00 EDT through 2026-08-10 17:00 EDT |
| Submission deadline | **2026-08-10 17:00 EDT / 21:00 UTC** |
| Judging period | 2026-08-17 10:00 EDT through 2026-08-31 17:00 EDT |
| Winners announced | On or around 2026-09-08 14:00 EDT |

On this snapshot date, three calendar days remain before submission closes.

### 3.2 Official challenge categories

1. **Agents That Do Real Work** — agents read DataHub context, take action,
   and write results back for the next person or agent.
2. **Metadata-Aware Code Generation & Development** — agents generate
   production data artifacts using DataHub context and place reviewable output
   in Git.
3. **Production ML Agents** — agents use ML lineage to protect production ML.
4. **Open / Wildcard** — other creative DataHub-founded applications.

The strongest primary category for Retirement Conductor is **Agents That Do
Real Work**. The product reads DataHub, performs a bounded Git/dbt mutation,
validates it, reconciles fresh context, writes a durable DataHub summary, and
enforces a producer decision. It also overlaps with Metadata-Aware Code
Generation, but code generation is intentionally not the main novelty.

### 3.3 Required DataHub use

The project must use the open-source DataHub platform together with at least
one of DataHub MCP Server, Agent Context Kit, DataHub Skills, or Analytics
Agent.

Retirement Conductor satisfies this through:

- DataHub Core v1.6.0;
- the pinned DataHub MCP Server v0.6.0;
- GraphQL/GMS and SDK fallbacks where complete paging or direct aspect reads
  are not exposed by MCP;
- stable publication and agent-visible read-back through DataHub.

Agent Context Kit, Analytics Agent, and DataHub Skills are not runtime
dependencies. Skills were reviewed as behavior references. The product does
not wrap stock search or lineage skills and claim that as novelty.

### 3.4 Submission requirements

The official rules require:

- a working software application that fits a challenge category;
- successful installation and consistent behavior on its intended platform;
- a public project URL that judges can access;
- a public source repository containing source, assets, and complete setup
  instructions;
- a visible Apache-2.0 license;
- an English text description;
- a publicly visible YouTube, Vimeo, or Youku demonstration video shorter
  than three minutes;
- disclosure of pre-existing work if used;
- a project newly built during the submission period;
- authorization and license compliance for third-party code, APIs, and data.

Sample outputs are recommended so judges can assess generated artifacts
without running the project. The tracked `artifacts/public/` evidence set
serves that purpose.

The GitHub repository was created on 2026-07-30, within the official build
period. GitHub reports the repository as public and the license as Apache-2.0.

### 3.5 Judging criteria

The five primary criteria are equally weighted:

1. **Use of DataHub** — meaningful use of graph/context and contribution back
   to DataHub where appropriate.
2. **Technical execution** — end-to-end functionality, implementation quality,
   and robustness.
3. **Originality** — clear value beyond features DataHub already ships.
4. **Real-world usefulness** — a credible problem for data, ML, or AI platform
   teams.
5. **Submission quality** — clear explanation, demo, README, and setup.

Meaningful open-source contributions to DataHub are a bonus criterion.

### 3.6 Prizes

- Grand Prize: $6,000, DataHub Town Hall presentation, promotion, and badge.
- Four Challenge Winners: $3,000 each, promotion, and badge.
- Two Honourable Mentions: $1,000 each and badge.
- Ten Most Valuable Feedback prizes: $50 each.
- Total advertised cash prizes: $20,500.

Each eligible project submission can win one project prize. The feedback
prizes are separate and require the official feedback submission.

### 3.7 Hackathon submission readiness

| Requirement or advantage | Status | Evidence or gap |
|---|---|---|
| Working application | Ready | Complete installed-wheel DataHub/Git/dbt reference and evidence |
| Meaningful DataHub use | Ready | Core graph, MCP, complete paging, direct aspect read, publication/read-back |
| Public source repository | Ready | Public GitHub repository |
| Apache-2.0 license | Ready | `LICENSE`; GitHub detects Apache-2.0 |
| New during submission period | Ready | Repository created 2026-07-30 |
| Setup and reproducibility instructions | Ready | README, runbooks, dossier, Make targets |
| Public working URL | Ready | Deployed dossier returned HTTP 200 on 2026-08-07 |
| English written description | Source material ready | README and dossier are extensive; Devpost form content is not verifiable here |
| Public video under three minutes | **Unverified / likely missing** | No YouTube, Vimeo, Youku, or demo-video URL found in tracked files |
| Devpost project saved/submitted | **Unverified** | No Devpost project URL or exported submission record found |
| Sample outputs | Ready | 56 public evidence artifacts plus deterministic HTML reports |
| Easy judge path | Ready in repository | MCP agent refusal trace and three-minute path are documented; video execution remains external |
| Open-source bonus contribution | Open, not yet accepted | DataHub MCP PRs #195 and #196 include regression tests; merge is external |
| Feedback prize submission | Unverified | No tracked confirmation; external form action is outside the repo |
| GitHub About homepage | Missing | GitHub API reports an empty `homepageUrl`, though README links the live site |
| Release tag | Missing | No Git tags are present; not a hackathon requirement, but a useful release signal |

### 3.8 Recommended judge-facing claim

> DataHub can tell you what a schema change may break. Retirement Conductor
> owns what happens next: it changes the one consumer it is authorized to
> change, validates that change with dbt, inventories again, writes the result
> back to DataHub, and refuses the producer change whenever the recorded
> evidence is incomplete or unsafe.

This claim is supported. Avoid claims that the system finds every consumer,
automatically migrates every platform, proves production safety, or has been
adopted by an independent customer.

## 4. Product definition

### 4.1 One sentence

Retirement Conductor moves known consumers off a legacy data field, verifies
the changes in each consumer's native environment, and prevents retirement
until the declared evidence is fresh and every in-scope consumer has an
acceptable disposition.

### 4.2 Human story

A data platform team wants to replace `orders.legacy_status` with
`orders.order_status`. The producing team can change the warehouse quickly,
but cannot safely answer:

1. What still depends on the old field?
2. Which consumers can be changed, and by whom?
3. Did each changed consumer still work?
4. Did a new consumer appear between inventory and retirement?

Today the answer is fragmented across catalogs, repositories, query history,
native validators, tickets, and memory. Retirement Conductor turns it into one
executable, replayable, evidence-scoped campaign.

### 4.3 User, beneficiary, buyer, and best fit

- **Primary operator:** data platform or analytics infrastructure engineer
  responsible for schema evolution.
- **Primary beneficiary:** owners of affected models, pipelines, reports, and
  other consumers.
- **Likely buyer:** leader accountable for data-platform reliability,
  migration throughput, and coordination cost.
- **Best fit:** DataHub already spans multiple systems; important
  transformations live in Git; external consumers exist; schema changes are
  frequent or expensive enough to need repeatable control.
- **Poor fit:** one repository and one warehouse already form the complete
  consumer boundary. dbt and normal review automation may be sufficient.

### 4.4 Product category

Verified change operations for the data stack, expressed through one complete
workflow: compatible column replacement and retirement.

It is not:

- a metadata catalog or replacement graph;
- a blast-radius report;
- a deprecation toggle;
- a generic coding agent;
- bulk text replacement;
- a ticket router or approval tracker;
- a universal guarantee about invisible consumers.

### 4.5 Promise and non-claims

Promise:

> All consumers observed through the declared sources have been accounted for
> under the recorded policy, or the retirement action is refused.

Non-claims:

- every company consumer is observable;
- metadata freshness equals source-data freshness;
- an owner approval proves semantic equivalence;
- a passing unrelated assertion closes a consumer;
- a hash proves authorship;
- DataHub can safely mutate every connected platform;
- readiness is permanent before the producer transaction commits;
- fixture or live-local evidence proves production or customer value.

## 5. Complete operational loop

```text
declare one exact field replacement
  -> resolve the field pair from live DataHub
  -> inventory through named, freshness-bounded evidence sources
  -> freeze identities, scope, permissions, pagination, versions, and blind spots
  -> plan one explicitly authorized Git/dbt change
  -> bind approval and operator confirmation to the exact plan digest
  -> apply only the allowlisted target under fresh source preconditions
  -> run dbt-native parse, seed, build, test, and semantic parity checks
  -> reconcile against equivalent fresh DataHub and native evidence
  -> reopen on late, stale, partial, ambiguous, drifted, or failed evidence
  -> publish and read back one durable DataHub summary
  -> issue one short-lived producer plan
  -> permit or refuse the producer-side action from the same canonical manifest
```

The model may interpret context and propose changes. Deterministic code owns
authorization, state transitions, evidence acceptance, and the final decision.

```text
The model proposes.
Native tools validate.
Deterministic policy decides.
```

## 6. Supported and unsupported scope

### Supported

- one legacy column and one compatible replacement in the same platform,
  instance, database, schema, and table;
- live DataHub identity resolution, schema, graph, and evidence reads;
- complete cache-bypassed GraphQL/GMS lineage inventory where supported;
- MCP-assisted context and publication read-back;
- one exact Git/dbt consumer identity;
- one reviewable, allowlisted repository mutation;
- dbt-native validation in an isolated disposable boundary;
- local deterministic campaign state and replay;
- fresh reconciliation;
- CLI, HTML, DataHub summary, and gate from one canonical manifest;
- a harmless reference producer sentinel.

### Unsupported or unclaimed

- automatic mutation of BI tools, notebooks, pipelines, ML models, or other
  non-Git consumers;
- cross-table replacement;
- production warehouse deletion;
- DataHub Cloud behavior;
- macOS, Windows, musl, distributed, shared, or multi-writer deployment;
- a product container;
- signed release provenance;
- hidden-consumer completeness;
- production graph and connector completeness;
- customer adoption or recurring commercial value.

### Explicitly removed

Looker was formerly planned as a second native executor. It never obtained the
required live evidence and added paid-service access cost without improving
the central DataHub hackathon claim. Decision D-038 reframed the product on
2026-08-02. Commit `8f5eb58` removed 7,566 lines of Looker runtime modules,
CLI commands, schemas, recipes, fixtures, tests, runbooks, and package surface.

Historical Looker observations remain in the evidence and decision logs only
when clearly labeled superseded. Looker must not be presented as supported.

## 7. Architecture

```text
Retirement specification
          |
          v
Deterministic campaign engine
     | evidence read          | authorized action
     v                        v
DataHub boundary         Git/dbt boundary
     |                        |
     +---------- receipts ----+
                   |
                   v
        single-writer SQLite store
             |             |
             v             v
       DataHub summary   CLI / HTML / producer gate
```

### 7.1 Authority boundaries

| Concern | Authority | Retirement Conductor's role |
|---|---|---|
| Warehouse/schema identity | Warehouse plus DataHub metadata | Resolve and record exact mapping |
| Cross-system inventory | DataHub within declared scope | Page fully; retain freshness, permissions, limits |
| Repository content | Git | Hash, branch, constrain, and preserve reviewability |
| dbt correctness | dbt runtime and project tests | Invoke exact native commands; retain redacted receipt |
| Non-repository consumers | Their native systems | Keep them blocking until valid external closure evidence |
| Campaign transition | Deterministic policy | Own legal states and refusal decisions |
| In-progress transaction state | Local SQLite store | Persist events, attempts, evidence, plans, receipts |
| Shared campaign context | DataHub document/context surface | Publish stable summary and verify read-back |
| Destructive producer mutation | Separately privileged workflow | Supply a one-time enforceable gate, not credentials |

DataHub is not the campaign transaction database. Its indexing and metadata
write behavior are eventually consistent and do not provide the local
compare-and-swap semantics the campaign needs.

### 7.2 Runtime shape

- Python 3.11+ command-line package;
- standard-library SQLite campaign store;
- append-oriented events plus materialized current state;
- deterministic canonical JSON and SHA-256 integrity digests;
- file-backed redacted artifacts;
- concrete DataHub and Git/dbt boundaries;
- generated, self-contained HTML reports;
- explicit single-writer, path-bound local deployment.

There is no generic adapter SDK, hosted control plane, worker fleet, scheduler,
service mesh, or distributed database.

### 7.3 Core implementation modules

| Area | Primary files |
|---|---|
| CLI and entry point | `src/retirement_conductor/cli.py`, `__main__.py` |
| Specification and schemas | `specification.py`, `schemas.py`, `records.py` |
| Determinism and time | `canonical.py`, `clock.py` |
| State and events | `state.py`, `events.py`, `store.py` |
| Policy and refusal vocabulary | `policy.py`, `refusals.py`, `vocabulary.py` |
| DataHub | `datahub.py`, `datahub_http.py`, `datahub_config.py`, `mcp_http.py` |
| Git/dbt | `git_dbt.py`, `git_dbt_config.py`, `git_dbt_workflow.py` |
| Reconciliation/publication/gate | `reconciliation.py`, `publication.py`, `gate.py` |
| Operator views | `operator.py` |
| Benchmark | `dataset_registry.py`, `benchmark_data.py`, `benchmark_oracle.py` |
| Deployment/reference | `deployment.py`, `reference.py` |
| Path safety | `paths.py` |

The repository currently has 33 top-level Python source modules, 35 Python
test files, 28 Python scripts, 18 JSON schemas, and 56 tracked public evidence
artifacts. `src`, `tests`, and `scripts` contain about 32,242 Python lines.

## 8. Campaign contracts

### 8.1 Evidence envelope

Every source records:

- required or optional status;
- `COMPLETE`, `PARTIAL`, `UNKNOWN`, `UNAVAILABLE`, or `STALE`;
- source and client versions;
- exact scope, traversal direction, hop count, filters, pages, and counts;
- capture time and native freshness;
- effective principal and permission scope without secrets;
- limitations and blind spots;
- raw/redacted artifact digests.

`COMPLETE` means the declared bounded request completed. It never means global
visibility. A required source must be complete and fresh for readiness.

### 8.2 Consumer identity and mutation

A mutable consumer must map one-to-one between its DataHub identity and exact
native Git/dbt identity. Display names and aliases assist discovery but never
authorize mutation. Zero or multiple matches refuse.

Apply requires all of:

- approved plan digest;
- approval bound to the campaign, source, target, and capability;
- exact operator-confirmed current plan digest;
- fresh branch, commit, file, node, and content fingerprints;
- exact target allowlist;
- explicit apply capability.

Planning cannot mutate. Outcome-unknown operations are reread before any retry.
Compensation refuses to overwrite intervening work.

### 8.3 Consumer dispositions

- `DISCOVERED`
- `IDENTIFIED`
- `CHANGE_PROPOSED`
- `APPLIED`
- `VALIDATED`
- `REMOVED`
- `NOT_APPLICABLE`
- `WAIVED`
- `OPAQUE`
- `UNRESOLVED`
- `STALE`
- `FAILED`

Default closure accepts only `VALIDATED`, verified `REMOVED`, and proved
`NOT_APPLICABLE`. A waiver is explicit residual risk, not successful migration.

### 8.4 Campaign lifecycle

```text
PROPOSED -> INVENTORIED -> MIGRATING -> RECONCILING -> READY -> RETIRED
```

`BLOCKED` is reachable from every pre-retirement state. A blocked campaign can
resume after new evidence. `RETIRED` is immutable; corrections use a linked
follow-up campaign. New inventory never imports a prior closure disposition.

### 8.5 Final decisions

The policy emits exactly one:

- `READY_TO_RETIRE` — all required evidence is complete and fresh, every
  in-scope consumer is acceptably closed, and reconciliation found no new one;
- `REVIEW_REQUIRED` — automated evidence is sufficient but an explicit human
  semantic or authority decision remains;
- `BLOCKED` — a required source, identity, permission, validator, approval, or
  other input is unavailable or inconclusive;
- `UNSAFE` — a known active, failed, stale, late, or otherwise unacceptable
  consumer remains.

The producer gate exits zero only for `READY_TO_RETIRE`.

### 8.6 Stable refusal families

| Prefix | Meaning |
|---|---|
| `SPEC_` | invalid or unsupported intent/replacement |
| `AUTH_` | authorization, approval, or capability missing |
| `EVIDENCE_` | unavailable, partial, stale, or unverifiable evidence |
| `IDENTITY_` | missing, ambiguous, or inconsistent identity |
| `SOURCE_` | source changed or native precondition failed |
| `DATASET_` | benchmark source unpinned, unlicensed, corrupt, or unexpected |
| `SCOPE_` | actual target exceeds plan or allowlist |
| `APPLY_` | mutation failed or was partial |
| `VALIDATION_` | native validation failed or was inconclusive |
| `COMPENSATION_` | recovery failed or was unsafe |
| `RECONCILIATION_` | graph refresh or comparison failed |
| `POLICY_` | campaign or consumer cannot legally close |
| `INTEGRITY_` | schema, digest, event, or artifact mismatch |
| `RUNTIME_` | clock, state, writer, isolation, or runtime failure |
| `GATE_` | final provenance, freshness, state, or plan check failed |

## 9. DataHub implementation boundary

### Read path

- inspect live capabilities rather than assume Core and Cloud are identical;
- resolve exact entities from live search instead of predicting URNs;
- retrieve schemas, owners, lineage, paths, and permitted query context;
- page to termination using the strongest available surface;
- request the lineage cache bypass and retain whether the server reports
  cached results;
- treat incomplete paging, cache uncertainty, permissions, staleness, and
  missing freshness as explicit limitations or refusals.

The supported MCP field-lineage helper cannot bypass cache, so it may qualify
a consumer claim but cannot exclude a consumer from the complete GMS result.

### Write path

- write one idempotently bound campaign summary;
- update the same logical document;
- poll the agent-visible read only within a bound;
- never repeat the write merely to obtain visibility;
- never treat write success as proof of exact publication;
- do not mutate dataset lifecycle state through the campaign publisher.

## 10. Git/dbt execution boundary

The concrete executor implements:

```text
preflight -> discover identity -> snapshot -> plan -> apply
          -> validate -> compensate if required -> emit receipt
```

The validation boundary treats repositories, macros, hooks, packages,
generated content, and subprocesses as untrusted input. On the supported Linux
path, dbt runs in a copied bubblewrap workspace with no host home, source
repository, or network namespace mounted, plus constrained environment and
resources.

Successful validation includes the declared native operations and semantic
tests. A successful API or Git operation alone is not validation.

## 11. Evidence-quality benchmark

Phase 06 replaced the abandoned paid Looker boundary with a deeper,
reproducible DataHub evidence-quality benchmark.

### 11.1 Official inputs

All assets are pinned to `datahub-project/static-assets` commit:

`a6479c691dd2a40dd89563396d9c8b2b28bee83c`

| Asset | Purpose | License boundary |
|---|---|---|
| `fiction-retail` database | primary relational field-replacement corpus | CC0 1.0 |
| `healthcare` database | deterministic faults and branch-selective impact | CC0 1.0 |
| `nyc-taxi` clean database | clean freshness control | public-domain source with recorded transformed-asset terms |
| `nyc-taxi` stale database | native data freshness versus metadata freshness | same boundary |

The first verified acquisition downloaded 312,086,528 bytes to an ignored
content-addressed cache. URL, full revision, reviewed license evidence, byte
size, SHA-256, SQLite header, and allowed archive members are all pinned. The
package contains the registry and schemas, not the database bytes. Later
verification can run strictly offline.

Registry digest:
`sha256:b0a4c716c932df7967453ce66a59863b7dc6e79ad39b46fff69464774176c6e4`.

### 11.2 Deterministic synthetic corpus

- seed: `20260802`;
- accepted profile: `medium`;
- 2,500 selected orders;
- 2,355 customers;
- 5,765 order items;
- 3,400 products;
- 499 suppliers;
- 7,826 inventory rows;
- 15 warehouses;
- 1,983 shipments;
- 203 returns;
- 151 promotions;
- all nine source status categories retained;
- zero violations across keys, 11 foreign-key relationships, temporal
  constraints, nonnegative totals, replacement null checks, and clean
  `legacy_status = order_status` parity.

The private fault manifest plants 25 rows each, or 1%, for:

- replacement null inflation;
- valid-category semantic drift;
- unmapped replacement values.

Twin generations matched byte-for-byte across all 16 artifacts. The generator
receipt digest is
`sha256:bcda2b5a4ed0b4f133b0b130ca0ffad1ef8735685e2f9521e84dcb94b811b83a`.

### 11.3 Independent oracle

The oracle does not import campaign policy. It independently declares graph
membership, fault impact, evidence state, expected decision, and refusal codes.
An intentionally corrupted expectation was rejected, which helps establish
that the evaluator is not merely agreeing with itself.

Oracle digest:
`sha256:aa07af1bf4d416a7729ce0a39a8fccee9766cd23153b844b09b000b7a71c25f5`.

### 11.4 Fourteen truth scenarios

| Scenario | Expected decision | Key refusal behavior |
|---|---|---|
| Clean isolated replacement | `READY_TO_RETIRE` | one verified dbt consumer; no refusal |
| Ambiguous native/DataHub identity | `BLOCKED` | `IDENTITY_AMBIGUOUS` |
| Incomplete pagination | `BLOCKED` | pagination and required-source refusal |
| Stale native data with fresh metadata | `BLOCKED` | required source incomplete |
| Rich graph with opaque consumers | `UNSAFE` | opaque consumer |
| Late consumer | `UNSAFE` | discovered consumer plus reconciliation reopening |
| Table-only lineage | `UNSAFE` | remains opaque; not upgraded to field proof |
| Incompatible replacement type | `UNSAFE` | replacement incompatibility |
| Unmapped replacement value | `UNSAFE` | native receipt failure |
| Replacement null inflation | `UNSAFE` | native receipt failure |
| Semantic drift | `UNSAFE` | native receipt failure |
| Healthcare selective impact | `UNSAFE` | affected branches fail |
| Ownership/context without validation | `UNSAFE` | metadata does not close consumer |
| Disappearing legacy edge | `UNSAFE` | stale consumer; disappearance is not closure |

Observed result: **14/14 matched**, **zero false readiness**, and **1.0 exact
expected-consumer recall**.

### 11.5 Native validation result

The approved apply changed exactly:

`models/orders_status_summary.sql`

dbt 1.12.0 parse, seed, build, and test passed on the clean corpus. The three
planted faults failed for the expected native reasons:

- null inflation: `not_null` plus source parity;
- semantic drift: source parity;
- unmapped category: accepted-values plus source parity.

The benchmark exposed an important design correction: consumer-output
equivalence alone can accept a replacement that is itself wrong. The final
contract therefore validates source-level legacy/replacement parity separately
from migrated-consumer equivalence.

### 11.6 Observed official-data discrepancy

Read-only probes found that the pinned NYC taxi stale bytes contain a nine-day
native gap from 2016-03-01 to 2016-03-10 and no zero-trip mart row. The upstream
README described a three-day gap and an empty load. Decision D-040 correctly
made checksum-verified bytes, not descriptive prose, control the oracle.

### 11.7 Live-local integration result

- DataHub Core directly reread the exact schema, field lineage, owner, domain,
  tag, glossary term, and quality assertion.
- The isolated campaign reached `READY_TO_RETIRE`.
- One DataHub publication was written and read back without lifecycle change.
- One short-lived producer plan wrote exactly one harmless sentinel.
- A late Spark consumer reopened the campaign to `UNSAFE`.
- A rich graph with dbt and table-only Tableau consumers remained `UNSAFE`.
- Three full live-local runs had different honest time-bound digests but the
  same semantic digest:
  `sha256:c60c2a91bc5202f794357052833598e1bd824200ffe047f2b51d1b77f6d3ed54`.

Canonical Phase 06 evidence digest:
`sha256:b930045d5769c9b7d938f5079dd4a37e4621b23796a0fdf45ad2ddd34e20e4b9`.

## 12. Phase ledger

| Phase | State | What was proved | Tested commit |
|---|---|---|---|
| 00 — Foundation | Complete | strict schemas, refusal fixtures, package smoke test | `6692a3c` |
| 01 — Campaign kernel | Complete | deterministic event replay, SQLite resume, state/refusal matrix | `30173f1` |
| 02 — DataHub evidence | Complete | exact live fields, 31 consumers over seven pages, stable document read-back | `19bebb9` |
| 03 — Git/dbt execution | Complete | exact cross-source identity, one-file apply, dbt validation, compensation, retry | `3ca39a1` |
| 04 — Reconciliation/gate | Complete | ready campaign, late reopening, rich refusal, one-time producer sentinel | `25466a9` |
| 05 — Operator experience | Complete | four-decision CLI/HTML parity, redaction, keyboard/mobile/a11y proof | `ae62486` |
| 06 — Evidence benchmark | Complete | pinned data, deterministic truth, 14/14, zero false readiness | `8f5eb58` |
| 07 — Security/reliability | Complete | least privilege, fault matrix, backup/restore, copied-store refusal, scans | `6e4ca87` |
| 08 — Deployment/adoption boundary | Engineering complete | reproducible package, four Python installs, installed live reference, lifecycle | `c3440b2` |

No phase is active. The next acceptance target is optional follow-on RC-018,
not another engineering phase.

## 13. Requirements status

| ID | Requirement | Status |
|---|---|---|
| RC-001 | exact replacement specification, evidence, validation, authorization | Satisfied |
| RC-002 | durable events, deterministic replay, interruption-safe resume | Satisfied |
| RC-003 | exactly four deterministic decisions | Satisfied |
| RC-004 | live DataHub identity resolution without predicted identity | Satisfied |
| RC-005 | bounded DataHub evidence envelope | Satisfied |
| RC-006 | DataHub materially expands scope and changes outcome | Satisfied |
| RC-007 | stable DataHub publication and agent-visible read-back | Satisfied |
| RC-008 | exact mutable native identity | Satisfied |
| RC-009 | guarded, approved Git/dbt target mutation | Satisfied |
| RC-010 | dbt-native validation and semantic checks | Satisfied |
| RC-011 | equivalent fresh reconciliation and late reopening | Satisfied |
| RC-012 | same policy in failure-closed producer gate | Satisfied |
| RC-013 | CLI, report, publication, gate from one manifest | Satisfied |
| RC-014 | understandable conditions and recovery actions | Satisfied |
| RC-015 | former live Looker requirement | Retired/superseded |
| RC-016 | least privilege, tampering, fault, concurrency, recovery | Satisfied for supported local scope |
| RC-017 | clean install, configure, upgrade, restore, remove | Satisfied |
| RC-018 | independent operator and recurring value | **Not run / not satisfied** |
| RC-019 | official-data benchmark and zero false readiness | Satisfied |

## 14. Evidence summary

### 14.1 DataHub consequence

- A preceding experiment found one repository consumer versus 35 DataHub graph
  consumers and reversed an allowed decision to refused.
- Product Phase 02 independently found one configured repository reference
  versus 31 live graph consumers, a conservative expansion of at least 30.
- DataHub is therefore material to the product claim, not decorative metadata.

### 14.2 End-to-end positive and refusal paths

- The isolated one-consumer campaign can close inside its exact envelope.
- The producer gate wrote one sentinel only after fresh reconciliation,
  verified publication, trusted provenance, and an exact issued plan.
- Replay, wrong writer/run, source drift, replacement drift, unavailable
  DataHub, tampered validation, late consumers, rich graphs, and missing state
  all refused without a second action.
- A late consumer increased membership and changed the same campaign from
  `READY_TO_RETIRE` to `UNSAFE`.

### 14.3 Operator experience

- CLI renders all four policy decisions.
- `inspect`, `explain`, local HTML, and public HTML share one presentation
  model derived from the canonical manifest.
- Public redaction is structural, not a string scrub.
- Desktop and 360-pixel mobile layouts passed.
- Fifteen controls were keyboard reachable.
- Two axe-core audits reported zero violations and zero incomplete checks.
- A fixture with all consumers closed still renders `BLOCKED` because fixture
  evidence cannot satisfy live policy.

### 14.4 Security and reliability

Post-removal Phase 07 observed:

- 53 security tests passed;
- 47 fault tests passed;
- 40 recovery tests passed;
- plan-only Git/dbt could not apply;
- source content could not expand authority;
- a mode-0600 backup reproduced the canonical manifest and schema versions;
- a byte-valid copied store refused before database mutation;
- zero vulnerability findings across 6 runtime and 18 all-group packages at
  the captured advisory point;
- 18 reviewed licenses accepted;
- 20 SHA-256-bound lock records verified;
- 302 text files scanned for secrets;
- 56 public artifacts inspected.

Phase 07 digest:
`sha256:38ca5631665d6b3402b8b07226c49a3531490a6e3adcb95053d4e671c432cc23`.

### 14.5 Evidence modes

- `live` or `live local`: observed against the named running tool or service;
- `fixture`: deterministic controlled input, never customer evidence;
- `replay`: reproduction of captured prior evidence;
- `analysis`: a source-backed conclusion with no runtime claim.

Live-local execution over fixtures proves integration mechanics within the
recorded envelope. It does not prove production coverage.

## 15. Release and deployment

### 15.1 Package

- package: `retirement-conductor`;
- version: `0.2.0`;
- Python: `>=3.11`;
- runtime dependencies: `jsonschema` and `PyYAML`;
- build backend: Hatchling;
- console entry point: `retirement-conductor`;
- wheel: 76 members;
- source archive: 85 members;
- source and wheel rebuild byte-for-byte;
- source archive rebuilds the same wheel;
- runtime lock is hash-bound;
- package is unsigned and says so.

Wheel digest:
`sha256:17e63b4c714362469268659ee39809319371958c415dc6209580540dd9b1d5f0`.

Source archive digest:
`sha256:9d70c9caedaa78e114875a7b06bd73f86fad172f12257ed67551246146a1576a`.

### 15.2 Executed compatibility

- Linux x86_64, glibc 2.43;
- CPython 3.11.15, 3.12.13, 3.13.14, and 3.14.4;
- DataHub Core/GMS v1.6.0;
- DataHub MCP v0.6.0 at commit
  `9a6946daa7d30eb481c82dd8ee5e15ae6526a3c9`;
- Git 2.53.0;
- dbt-core 1.12.0;
- dbt-duckdb 1.10.1;
- DuckDB 1.5.5;
- Docker 29.1.3;
- bubblewrap 0.11.1.

The exact MCP release tag matters. Provisioning the raw commit without its
tag caused the executable to report `0.0.1.dev1`; decision D-043 requires tag
`v0.6.0`, exact commit resolution, and self-reported version `0.6.0`.

### 15.3 Installed reference

- all 35 product operations used the clean installed wheel;
- zero operations imported the source checkout;
- preflight passed the `core-git-dbt` profile;
- local metrics were explicitly opted in and had no remote export;
- native dbt passed;
- isolated campaign reached `READY_TO_RETIRE`;
- publication read-back verified after two attempts;
- one sentinel executed;
- late campaign reopened to `UNSAFE`;
- a 41-consumer rich graph remained `UNSAFE`;
- the gate ledger recorded one executed and 12 refused attempts.

### 15.4 Upgrade, rollback, and removal

- upgrade from 0.1.0 to 0.2.0 advanced schema versions `[1]` to `[1,2,3]`
  without changing the campaign manifest;
- verified backup-based rollback restored the prior package/database pair;
- copied state refused as a different campaign authority;
- unconfirmed removal refused;
- confirmed removal deleted only the planned local product state;
- package uninstall is a separate explicit operation;
- in-place downgrade is unsupported.

Phase 08 engineering digest:
`sha256:c7b6b754380f3c01c411db7b847959e02bea2f8bfe0f8856bb144a4db5876d05`.

## 16. CLI surface

Top-level commands:

```text
deployment
reference
validate-spec
fixture
datahub
benchmark
campaign
adapter
producer
gate
report
```

Important operations include:

- `deployment preflight`, `removal-plan`, `remove-state`;
- `reference run`;
- `datahub preflight`;
- benchmark data acquire, verify, generate, and compare;
- campaign create, replay, evaluate, inventory, reconcile, publish,
  verify-publication, inspect, explain, resume, export, backup,
  verify-backup, and diagnostics;
- Git/dbt preflight, plan, authorize, apply, validate, and compensate
  operations; internal adapter contracts also perform identity discovery,
  snapshotting, and receipt emission;
- producer plan;
- producer gate;
- deterministic report build.

Run `uv run retirement-conductor --help` and the nested `--help` commands for
the exact current argument contract.

## 17. Public dossier

The standalone dossier lives at `site/public/retirement-conductor.html` and is
deployed through the `site/` application. The root route redirects to the
standalone document so the site and shareable artifact stay aligned.

The dossier includes:

- the problem and product claim;
- the seven-step operational loop;
- architecture and authority boundaries;
- all four decisions;
- supported and unsupported scope;
- phase evidence and benchmark results;
- official input provenance;
- the full refusal matrix;
- copyable verification commands;
- security and recovery boundaries;
- agent handoff instructions;
- explicit unproven limitations.

The dossier footer identifies product evidence snapshot `f8f533d` and says it
was updated on 2026-08-06. The current repository HEAD `e122491` contains the
subsequent site toolchain-hardening commit.

## 18. Repository and Git status

As observed on 2026-08-07:

- GitHub repository: `Arshgill01/RetirementConductor`;
- visibility: public;
- default branch: `main`;
- license detected by GitHub: Apache-2.0;
- created: 2026-07-30 03:47:35 UTC;
- last pushed commit: `e122491` on 2026-08-06 09:30:17 UTC;
- local HEAD: `e12249145d088b1b6ef39fa4240d72fbe6aa51bf`;
- `origin/main`: the same commit;
- worktree before this context file: clean;
- tags: none;
- GitHub homepage field: empty;
- repository topics: none.

Recent milestone commits:

| Commit | Meaning |
|---|---|
| `e122491` | harden public site build toolchain |
| `cac8ac2` | publish public technical dossier |
| `f8f533d` | record completion of DataHub-native goal |
| `c3440b2` | isolate independent adoption as follow-on |
| `6e4ca87` | close post-removal Phase 07 acceptance |
| `8f5eb58` | remove Looker release surface |
| `34df09e` | complete live evidence-quality campaign fixes |
| `ef02788` | generate deterministic benchmark corpus |
| `4148020` | verify pinned official DataHub datasets |
| `ac2e8a2` | reframe product around DataHub evidence quality |

The durable release acceptance is tied to behavior commit `c3440b2`: 183
tests, Ruff, formatting, strict mypy, repository validation, secret and
public-artifact review, reproducible builds, four clean installs,
upgrade/rollback/removal, installed-wheel reference, and `git diff --check`.

The current workspace, including this context document and both later
dossier/site commits, was revalidated on 2026-08-07:

- `make check` passed;
- Ruff lint passed;
- 96 Python files were already correctly formatted;
- strict mypy passed 68 source files;
- all 183 pytest cases passed;
- repository validation passed 178 required files, 52 Markdown files, and 148
  relative links;
- the secret scan passed 320 text files;
- public-artifact review passed all 56 files;
- source and wheel builds passed;
- `git diff --check` passed;
- `site/npm test` built the public site and passed all four rendered-output
  tests;
- `site/npm run lint` passed.

## 19. Test and build commands

### Fast package/reference path

```bash
uv sync --all-groups
uv run retirement-conductor --version
uv run retirement-conductor reference run
```

The built-in reference deliberately remains `BLOCKED` with
`EVIDENCE_MODE_NOT_LIVE`.

### Repository-wide verification

```bash
make check
```

This runs Ruff lint, Ruff formatting check, strict mypy, pytest, repository
validation, secret scanning, public-artifact review, source/wheel build, and
`git diff --check`.

### Benchmark

```bash
make phase06-data
make phase06-benchmark
make phase06-evidence
```

The first command can transfer about 312 MB on a cold cache. DataHub Core,
Docker, MCP, dbt, DuckDB, and local benchmark state are required for the full
live-local benchmark.

### Security and recovery

```bash
make test-security
make test-faults
make test-recovery
make phase07-evidence
```

### Packaging and installed reference

```bash
make package
make test-install
make test-upgrade
make test-reference-campaign
make phase08-evidence
```

### Public dossier

```bash
cd site
npm ci
npm test
npm run lint
```

## 20. Decision history

### Foundational accepted decisions

- D-001: complete one column-retirement vertical.
- D-002: DataHub is context/reconciliation, not transaction storage.
- D-003: command line and SQLite first.
- D-004: deterministic policy owns readiness.
- D-005: Git/dbt is the first native executor.
- D-007: destructive producer action remains separately privileged.
- D-008: no generic adapter framework before real evidence requires it.
- D-009: deterministic digests now; signing only with a threat model.
- D-010: one policy engine for CLI, report, publication, and gate.
- D-011: disappearing lineage is not closure.
- D-012: refusal is a successful product outcome.
- D-013: SQLite deployment is single-writer.
- D-014: uncertain native outcomes require source discovery before retry.
- D-015: Phase 04 proves both permission and refusal live locally.
- D-016: use standard YAML and JSON Schema implementations.
- D-017: canonical event replay outranks materialized state.

### Evidence and operator decisions

- D-018: choose MCP/GraphQL/SDK surfaces from observed Core capabilities.
- D-019: calculate cross-source expansion conservatively.
- D-020: Git/dbt mutation requires exact cross-source identity.
- D-021: validate untrusted dbt from a copied no-network boundary.
- D-022: issue and consume one producer plan per canonical manifest.
- D-023: page sparse DataHub lineage by individual graph degree.
- D-024: apply confirmation binds the reviewed plan digest.
- D-025: operator views remain canonical; public redaction is structural.
- D-030: recovery preserves the original bound store authority.
- D-032: ship the CLI as a wheel before adding a product container.
- D-033: state removal is separately planned and digest-confirmed.
- D-034: complete lineage inventory bypasses graph cache.
- D-035: poll publication visibility without repeating the write.
- D-036: release inputs stay separate from operational evidence.

### Current reframe and release decisions

- D-038: replace Looker proof with DataHub evidence-quality benchmark.
- D-039: pin official databases; distribute only the registry.
- D-040: observed pinned bytes outrank descriptive prose.
- D-041: validate replacement truth separately from consumer truth.
- D-042: delete the deprecated adapter instead of shipping dormant code.
- D-043: preserve the MCP release tag and exact commit identity.
- D-044: separate release engineering from independent adoption evidence.

### Superseded Looker decisions

D-006, D-026, D-028, D-029, the Looker-specific part of D-031, and D-037
remain historical only. They do not contribute to current acceptance.

## 21. Risk register summary

### Open or still needing external evidence

- **R-21 — adoption frequency:** open. Only an independent prospective
  operator can establish recurrence, friction, willingness, and buyer role.
- **R-22 — competitive convergence:** open. DataHub, Atlan, Datafold, dbt, or
  internal platforms may close the documented execution gap.
- **R-27 — trusted time:** still marked `testing` in the risk register even
  though local skew/expiry tests exist; deployment clock trust remains.
- **R-29 — recreated identity:** contained for Git/dbt but still calls for
  broader delete/recreate and recycled-display-name scenarios.
- **R-33 — policy/configuration/validator/authorization drift:** contained for
  the supported path but still requests broader benchmark drift exercises.

### Reframed

- **R-08 — adapter economics:** reframed. The product chose one concrete
  executor and stronger evidence instead of accumulating platform-specific
  adapters.

### Material residual boundaries despite contained local evidence

- catalog completeness and production ingestion latency;
- production identity collisions and connector naming changes;
- domain-specific semantic tests for each customer;
- a consumer appearing during the final external producer transaction;
- secret-provider, CI identity, host, signing, and storage controls;
- arbitrary dbt projects on non-Linux isolation boundaries;
- non-transactional remote mutation and compensation;
- unrecognized shared filesystems or distributed writers;
- DataHub Core/Cloud and future-version divergence;
- report/publication latency and resumability;
- production source-data sensitivity and redaction;
- the unavoidable race owned by a real separately privileged producer action.

### Documentation note

`STATUS.md` correctly says the engineering goal is complete, while a few risk
rows retain `testing` language for broader production/deployment cases. That
does not invalidate the bounded completion claim, but the distinction should
remain visible and the risk register should be normalized before any broader
“production-ready” claim.

## 22. Competitive position

The responsible current claim is:

> In the primary public documentation reviewed, no single product clearly
> combines DataHub-bounded field impact, guarded Git/dbt mutation, native
> semantic validation, fresh graph reconciliation, and a deterministic
> producer-side refusal gate with an explicit evidence-quality envelope.

This is qualified, not proof that no private or newer system exists.

| Product | Relevant strength | Current documented gap versus this workflow |
|---|---|---|
| DataHub | graph, context, ownership, lineage, contracts, incidents, MCP | does not visibly ship this complete native-mutation/receipt/gate loop |
| Atlan | lifecycle workflow, owners, communication, prioritization | reviewed workflow does not visibly bind native validation into one reconciled producer gate |
| Datafold | migration automation and strong parity validation | focused on platform/SQL migration, not this DataHub-bounded downstream field-retirement campaign |
| dbt Wizard | strong dbt understanding, refactoring, and validation | dbt-scoped; no cross-system campaign authority |

The moat is not code generation. It is the evidence and authorization protocol
that makes unrelated systems satisfy one continuously reconciled completion
criterion.

## 23. Product success measures

### Engineering/product behavior

- share of consumers with exact native identity;
- share closed by native validation, verified removal, or proved
  non-applicability;
- late or stale consumers caught before producer change;
- deterministic resume after interruption;
- false readiness count, which must remain zero in controlled truth;
- expected-consumer recall against a controlled graph;
- operator interventions per closed consumer.

### Customer value, not yet established

- reduction in manual inventory and coordination;
- migration completion without post-change breakage;
- reduction in time to a defensible producer decision;
- retirement campaigns completed instead of left indefinitely deprecated;
- recurrence, willingness to adopt, and presence of a budget owner.

Repository activity, phase completion, and fixture success do not establish
these customer measures.

## 24. Open questions

### Product and adoption

- How often do DataHub teams perform cross-system field retirement?
- Who operates the campaign and who owns the final producer change?
- Is the dominant pain discovery, migration, validation, coordination, or
  approval?
- Is the desired shape a product, DataHub application, CI action, or internal
  runbook?
- What evidence would a platform leader require before producer retirement?
- Can an independent operator complete the workflow without author repair?

### DataHub

- Which Core and Cloud versions matter first?
- Which paging and freshness surface remains most stable: MCP, GraphQL, or SDK?
- How should ingestion run identity bind to a graph snapshot?
- What is the best cross-edition campaign summary object?
- How should column identity survive connector renames and schema evolution?

### Native execution

- What minimum dbt test set proves meaningful domain equivalence?
- How should macros, generated SQL, non-default branches, and `SELECT *`
  appear in the evidence envelope?
- What external receipt can safely close a non-repository consumer?
- What real operator need would justify the second native executor?

### Deployment

- Is single-writer CLI operation sufficient in practice?
- Do teams need CI-only use, an embedded DataHub app, or a shared service?
- Which secret provider and trusted CI identity should bind producer plans?
- Is artifact signing needed, and who owns the key/recovery model?

## 25. Independent operator boundary (RC-018)

RC-018 is the smallest honest unfinished product requirement.

Required participant:

- one prospective operator who is independent of the author.

Required workflow:

- one recent field replacement or retirement on explicitly safe disposable
  resources, following `docs/EVALUATION.md` without undocumented author help.

Required observations:

- frequency of the underlying workflow;
- prior versus observed time, steps, and handoffs;
- author intervention;
- friction and operational burden;
- whether evidence changed a real decision;
- willingness to use, adopt, reject, or fund it;
- buyer or approver role.

The public artifact currently says `NOT_RUN` and `NOT_SATISFIED`. No secrets
are required. Raw notes remain outside Git; only a redacted observation using
`docs/templates/OPERATOR_OBSERVATION.md` should be committed.

One operator cannot prove broad demand. It can prove bounded independent
operability and give the first direct adoption evidence.

## 26. Hackathon strengths and weaknesses

### Strongest judging evidence

- **Use of DataHub:** DataHub changes the inventory and policy outcome, and the
  result is written back for later agents.
- **Technical execution:** real live-local Core, MCP, Git, dbt, SQLite,
  reconciliation, publication, recovery, packaging, and producer-gate paths.
- **Originality:** the product owns verified completion after impact analysis;
  it does not rebuild DataHub features.
- **Usefulness:** schema retirement is costly specifically when consumers span
  catalogs, repositories, and opaque systems.
- **Submission quality:** extensive dossier, reproducible commands, evidence
  ledger, public artifacts, and explicit non-claims.

### Biggest weaknesses before submission

1. No verified public demo video.
2. No verified Devpost submission/project URL.
3. The dossier is technically excellent but dense; a judge may never run the
   312 MB benchmark or read the full evidence ledger.
4. The MCP agent path is implemented, but the video must actually show its
   tool calls and the late-consumer decision reversal in the first minute.
5. The two upstream DataHub MCP PRs are open, not merged; do not present them as
   accepted contributions.
6. No independent operator result exists, so real-world usefulness must be
   argued from the problem and engineering evidence rather than adoption.
7. GitHub About currently omits the live homepage and topics.
8. There is no release tag, even though package 0.2.0 is fully evidenced.

## 27. Recommended three-minute demo

The video should optimize for judge comprehension, not enumerate every phase.

### 0:00–0:20 — problem and promise

Show `orders.legacy_status` and say:

> A repository search finds one consumer. DataHub finds the real cross-system
> blast radius. Retirement Conductor changes only what it is authorized to
> change, validates it natively, then refuses deletion unless fresh evidence
> closes.

### 0:20–0:45 — DataHub consequence

Show repository count `1` versus DataHub graph count `31` or the rich graph.
Emphasize that DataHub changes the decision rather than decorating the UI.

### 0:45–1:20 — real work

Show:

- exact DataHub-to-dbt identity;
- one approved file target;
- one-file diff;
- dbt parse/build/test result;
- accepted native receipt.

### 1:20–1:50 — reconciliation and write-back

Show the isolated campaign reaching `READY_TO_RETIRE`, stable DataHub summary
read-back, and exactly one producer sentinel.

### 1:50–2:20 — decisive failure case

Introduce a late Spark consumer. Show the same campaign reopen to `UNSAFE`,
the new refusal codes, and the gate exiting non-zero without another sentinel.

### 2:20–2:42 — benchmark credibility

Show the compact Phase 06 evidence:

- 14/14 scenarios;
- zero false readiness;
- 100% controlled recall;
- four checksum-pinned official assets;
- three native data-fault refusals.

### 2:42–3:00 — finish

> DataHub finds and remembers the cross-system context. Git and dbt remain
> native authorities. Retirement Conductor is the failure-closed protocol that
> turns them into one enforceable retirement decision.

End on the public URL and repository. Keep the video below 2:55 to avoid
platform timing and rule risk.

## 28. Recommended submission text skeleton

### Title

**Retirement Conductor — verified change operations for legacy data fields**

### Short description

Retirement Conductor uses DataHub to find the known consumers of a legacy
field, migrates the exact Git/dbt consumer it is authorized to change,
validates the change with dbt, reconciles fresh graph evidence, writes a
durable campaign summary back to DataHub, and refuses the producer change when
any known consumer or evidence source remains unsafe.

### Why it matters

Catalog impact analysis shows what might break, but it does not move those
consumers or prove that the migration works. A warehouse column can look
unused in its repository while still feeding dashboards, reports, notebooks,
pipelines, or models elsewhere. Retirement Conductor makes discovery,
mutation, native validation, reconciliation, and final enforcement one
evidence-scoped operation.

### DataHub use

The application resolves exact field identities from DataHub Core, performs
complete bounded lineage inventory through GraphQL/GMS with MCP context,
retains schema, ownership, quality, and limitation evidence, writes one stable
campaign summary, and verifies agent-visible read-back. DataHub expanded one
repository consumer into 31 graph consumers and changed the policy outcome.

### What is technically novel

- exact DataHub-to-native identity binding;
- guarded one-file Git/dbt mutation;
- source-native validation receipts;
- deterministic, failure-closed campaign policy;
- fresh reconciliation that can revoke readiness;
- a one-time producer plan and refusal gate;
- explicit evidence envelopes that never turn empty or partial results into
  safety.

### Evidence

The official-data benchmark uses four checksum-pinned DataHub assets and a
deterministic independent oracle. It matched all 14 expected scenarios with
zero false readiness and 100% expected-consumer recall in the controlled
graph. The clean path passed dbt and reached readiness; late, stale, partial,
ambiguous, table-only, incompatible, quality-failing, and opaque-rich paths
refused.

### Honest boundary

Git/dbt is the sole automated mutation boundary. Other DataHub consumers stay
blocking until independently validated, removed, or proved non-applicable.
The evidence is live-local over official and generated fixtures, not a claim
of production completeness or customer adoption.

## 29. Immediate action plan before the deadline

### Critical: submission completion

1. Confirm that the entrant is registered and that a Devpost draft exists.
2. Record the selected category as **Agents That Do Real Work**.
3. Produce and upload the public demo video under three minutes.
4. Fill the Devpost text fields from the skeleton above.
5. Add the live dossier and public GitHub repository URLs.
6. Confirm the repository license is visible in the GitHub About section.
7. Submit before 2026-08-10 21:00 UTC; do not rely on last-minute upload.

### Critical: final validation

1. Run `make check` on current HEAD plus this documentation change.
2. Run `npm test` and `npm run lint` in `site/`.
3. Inspect the deployed site after any publication.
4. Perform the exact short judge path from a clean environment.
5. Check every video and repository link in an incognito browser.

### High value, low effort

1. Set the GitHub About homepage to the public dossier.
2. Add useful repository topics such as `datahub`, `dbt`, `data-lineage`,
   `schema-migration`, and `data-engineering`.
3. Create a `v0.2.0` release tag only if release ownership and current artifact
   identity are intentionally confirmed.
4. Add the demo-video and Devpost URLs to the README after publication.
5. Put a 60-second quick-judge path near the top of the README.

### Optional if time remains

1. Run one independent operator observation for RC-018 without manufacturing
   or coaching the result.
2. Monitor DataHub MCP PRs #195 and #196 and answer maintainer feedback without
   expanding their scope.
3. Submit the official feedback form with the reproduced pagination defect and
   actionable DataHub/MCP findings.

## 30. Definition of done from here

### Engineering goal

Already complete within the bounded claim. Do not reopen scope merely to add
platform count or polish.

### Hackathon submission

Complete only when:

- Devpost draft fields are complete;
- category is selected;
- public repository and site links work;
- public video is uploaded and under three minutes;
- licensing and build-period disclosures are correct;
- setup instructions work on the intended platform;
- the final text makes the DataHub/MCP dependency and agent action obvious;
- the submission is actually submitted before the deadline;
- a final screenshot or confirmation is retained outside the repository if it
  contains account information.

### Product/adoption goal

Still incomplete until RC-018 records one honest independent operator result.
That is follow-on evidence, not a reason to weaken or delay the hackathon
engineering claim.

## 31. Key files and artifacts

### Control and truth

- `GOAL.md`
- `STATUS.md`
- `PLAN.md`
- `docs/PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/CONTRACTS.md`
- `docs/REQUIREMENTS_TRACEABILITY.md`
- `docs/RISKS.md`
- `docs/DECISIONS.md`
- `docs/EVIDENCE_LEDGER.md`

### Hackathon and benchmark

- `docs/phases/06-data-quality-benchmark.md`
- `docs/runbooks/DATA_QUALITY_BENCHMARK.md`
- `fixtures/data-quality/datasets.json`
- `artifacts/public/phase06/phase06-evidence.json`
- `artifacts/public/phase06/refusal-matrix.json`
- `artifacts/public/phase06/oracle-evidence.json`
- `artifacts/public/phase06/datahub-evidence.json`
- `artifacts/public/phase06/native-validation-evidence.json`

### Security and release

- `docs/SECURITY_MODEL.md`
- `SECURITY.md`
- `docs/runbooks/RECOVERY.md`
- `docs/runbooks/DEPLOYMENT.md`
- `docs/COMPATIBILITY.md`
- `artifacts/public/phase07/phase07-evidence.json`
- `artifacts/public/phase08/phase08-preacceptance-evidence.json`
- `artifacts/public/phase08/operator-boundary.json`

### Adoption

- `docs/EVALUATION.md`
- `docs/templates/OPERATOR_OBSERVATION.md`
- `docs/OPEN_QUESTIONS.md`

### Public pitch

- `README.md`
- `docs/runbooks/AGENT_DEMO.md`
- `.agents/skills/retirement-conductor-agent/SKILL.md`
- `.codex/config.toml`
- `artifacts/public/agent/agent-acceptance.json` (after acceptance promotion)
- `site/public/retirement-conductor.html`
- `site/README.md`

## 32. Final bottom line

Retirement Conductor has crossed the important engineering threshold: it is a
working, tested, packaged, failure-closed DataHub application rather than a
mockup, impact report, or generated diff. Its strongest proof is not that a
clean campaign can become ready; it is that new, stale, ambiguous, partial,
opaque, or natively invalid evidence reliably revokes readiness and prevents
another producer action.

The current bounded claim is defensible:

- DataHub materially expands the known blast radius;
- one exact Git/dbt consumer is safely changed and natively validated;
- fresh reconciliation can reverse the decision;
- one canonical campaign state feeds the CLI, report, DataHub summary, and
  producer gate;
- official and deterministic truth sets produced 14/14 expected decisions and
  zero false readiness;
- the release is reproducible and installable across four Python series.

The project must not claim what it has not proved:

- universal consumer discovery;
- automatic migration outside Git/dbt;
- production warehouse retirement;
- DataHub Cloud or broad platform portability;
- independent adoption, recurring value, or buyer willingness.

As of 2026-08-07, engineering is not the deadline risk. The remaining critical
path is the public video, Devpost entry, compact judge narrative, and final
current-HEAD validation.
