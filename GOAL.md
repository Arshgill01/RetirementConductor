# DataHub-native implementation goal

This file is the controlling execution contract for the current Retirement
Conductor run. It supersedes the former requirement for a live Looker adapter.
The former Looker implementation was removed from the supported source and
package at checkpoint `8f5eb58`; only clearly superseded historical decisions
and evidence remain. It is not part of the supported product, acceptance path,
or completion claim.

## Exact objective

> Reframe Retirement Conductor as a DataHub-native,
> evidence-quality-first field-retirement system with Git/dbt as its sole
> automated consumer mutation boundary; remove Looker from the supported
> product and completion contract; and build a reproducible benchmark from
> official DataHub hackathon datasets plus deterministic synthetic truth sets
> that proves inventory, native validation, reconciliation, and producer
> refusal without external paid services.

## Current truth

The previous plan used Looker to prove that one campaign protocol could
coordinate two heterogeneous native mutation systems. That experiment became
an external-access dependency whose operational cost exceeded its value for
this submission. The decision is to stop pursuing it, not to replace missing
live evidence with fixtures.

The product already has stronger evidence for a narrower and useful claim:

- live DataHub Core resolved the exact legacy and replacement fields;
- complete paged lineage expanded one repository consumer to 31 graph
  consumers and changed the policy outcome;
- one exact Git/dbt consumer crossed guarded mutation, dbt-native validation,
  compensation, and idempotent reapply;
- fresh DataHub reconciliation reopened a previously ready campaign when a
  late consumer appeared;
- a stable DataHub summary was written and read back;
- the same canonical manifest drove CLI, HTML, publication, and an enforceable
  producer-side refusal gate;
- clean installation, upgrade, rollback, backup, restore, and removal were
  exercised from the packaged wheel.

Those results prove the complete first vertical. They do not prove that every
DataHub consumer can be mutated automatically, and the new product no longer
claims that. Git/dbt is the only automated mutation boundary. Other DataHub
consumers remain exact, explainable blockers until they have an accepted
external receipt, a verified removal, or a proved non-applicability record.

## Instruction order

Before non-trivial work, read:

1. `AGENTS.md`;
2. this file;
3. `STATUS.md`;
4. `README.md`;
5. `docs/PRODUCT.md`;
6. `PLAN.md`;
7. the active phase contract;
8. `docs/REQUIREMENTS_TRACEABILITY.md`;
9. relevant architecture, contracts, risks, decisions, access, evidence, and
   research documents.

Safety and evidence truth outrank convenience. This file controls the active
end-to-end run; phase files define acceptance details but never authorize
stopping after one intermediate output.

## Required product outcome

```text
declare one exact field replacement
  → resolve the field pair from live DataHub
  → inventory through a named, freshness-bounded evidence envelope
  → change only an explicitly authorized Git/dbt consumer
  → validate with dbt-native parse, build, and semantic tests
  → reconcile against fresh DataHub and data-quality evidence
  → reopen on late, stale, partial, ambiguous, or failed evidence
  → publish and read back one durable DataHub summary
  → permit or refuse the producer-side action from the same manifest
```

The system must never turn an opaque dashboard, pipeline, notebook, model, or
query into a closed consumer merely because no native adapter exists. The
absence of Looker is a smaller automation scope, not a weaker safety policy.

## Scope control

Looker is out of scope everywhere:

- no Looker instance, trial, API credential, query, mutation, ingestion
  recipe, or acceptance evidence is required;
- no Looker-specific deployment profile, schema, CLI command, package module,
  fixture, test, or runbook may remain in the supported release surface;
- no completion rule may depend on a second native adapter;
- historical Looker decisions and evidence may remain only when labeled
  superseded and excluded from current acceptance;
- large or security-sensitive deletions must be performed in focused commits
  with package, migration, and replay compatibility inspected afterward.

Do not replace Looker with another paid BI instance. Cross-platform metadata
can still be present in DataHub, but only Git/dbt is mutated by the product.

Do not add a generic adapter framework, hosted service, distributed scheduler,
custom SQL compiler, custom metadata graph, broad asset taxonomy, or visual
control plane. The benchmark exists to deepen the complete field-retirement
vertical, not broaden product nouns.

## Phase authority

Each phase is an acceptance contract:

1. [Phase 00 — foundation](docs/phases/00-foundation.md)
2. [Phase 01 — campaign kernel](docs/phases/01-campaign-kernel.md)
3. [Phase 02 — DataHub evidence](docs/phases/02-datahub-evidence.md)
4. [Phase 03 — Git/dbt execution](docs/phases/03-git-dbt-execution.md)
5. [Phase 04 — reconciliation and gate](docs/phases/04-reconciliation-gate.md)
6. [Phase 05 — operator experience](docs/phases/05-operator-experience.md)
7. [Phase 06 — evidence-quality benchmark](docs/phases/06-data-quality-benchmark.md)
8. [Phase 07 — security and reliability](docs/phases/07-security-reliability.md)
9. [Phase 08 — deployment and adoption](docs/phases/08-deployment-adoption.md)

## DataHub hackathon resource audit

The authoritative resource list is the
[Build with DataHub hackathon resources page](https://datahub.devpost.com/resources).
The new work must use the resources that strengthen this product and record
why the others are unnecessary.

| Resource | Current use | Decision |
|---|---|---|
| DataHub Core | live disposable Core v1.6.0 already exercised | keep as the required context runtime |
| DataHub MCP Server | pinned v0.6.0 already exercised | keep for agent-visible reads and document read-back |
| DataHub APIs/SDK | GraphQL and SDK fallbacks already exercised | keep for complete paging, direct aspect reads, ingestion, and publication |
| DataHub Skills | researched, not a runtime dependency | use as behavior reference; do not wrap stock search/lineage skills as product novelty |
| Agent Context Kit | not used | evaluate only if it exposes evidence unavailable through the pinned MCP/API boundary |
| Analytics Agent | not used | exclude; text-to-SQL is outside field-retirement control |
| `showcase-ecommerce` datapack | used only in the preceding experiment | retain as historical baseline; do not make its Looker-bearing graph a new acceptance dependency |
| `bootstrap` datapack | not used | optional smoke test only; too shallow for evidence-quality acceptance |
| `nyc-taxi` | not used | adopt for freshness gaps and empty-load truth that metadata ingestion time alone cannot reveal |
| `healthcare` | not used | adopt for deterministic quality failures and selective downstream impact on a forked graph |
| `fiction-retail` | not used | adopt as the primary clean, relational, domain-aligned base for the field-retirement benchmark |

Official dataset inputs must be pinned to an upstream revision, license
checked, checksum verified, and cached outside Git when large. The repository
must never silently download moving `main` content during an acceptance run.

## Data focus

### Primary: fiction-retail field-retirement corpus

Use the official CC0 fiction-retail data as the realistic base because its
orders, order items, shipments, returns, promotions, customers, inventory, and
warehouse relationships match the product story. Derive a versioned
`legacy_status` to `order_status` campaign without modifying the upstream
asset in place.

The derived corpus must support:

- a clean compatibility case where the two fields are semantically equal;
- value drift, null inflation, unmapped categories, and type drift;
- an exact dbt consumer with compiled lineage and semantic tests;
- multiple downstream graph consumers that remain opaque and blocking;
- a late consumer introduced only after the first reconciliation;
- before/after source fingerprints and an independently calculated parity
  oracle.

### Secondary: nyc-taxi freshness truth

Use the official clean and planted-staleness variants to prove that a recently
ingested DataHub entity can still represent stale underlying data. Capture the
three-day staging/mart gap and empty-load day as source-native truth. A fresh
catalog timestamp must not satisfy data freshness when the campaign requires a
native data-time check.

### Secondary: healthcare impact-selectivity truth

Use the official deterministic healthcare corpus to exercise negative billing,
null names, invalid ages, and swapped dates across a forked lineage graph. The
benchmark must distinguish which downstream mart each defect affects. It must
not claim that an owner, tag, glossary term, or unrelated passing assertion
closes an affected consumer.

## Synthetic data quality standard

New synthetic data is accepted only when it is a truth-bearing benchmark, not
decorative volume. Every generated scenario must include:

1. **Determinism** — fixed generator version and seed, stable ordering, and
   byte-for-byte reproducible manifests.
2. **Causal structure** — explicit upstream-to-downstream transformations,
   field mappings, and temporal ordering rather than random independent rows.
3. **Relational integrity** — declared primary/foreign-key expectations and
   measured orphan, duplicate, and null rates.
4. **Plausible distributions** — documented status frequencies, order values,
   time intervals, and correlations with bounded statistical checks.
5. **Clean control** — a known-good twin for every planted-failure variant.
6. **Fault provenance** — exact injected row IDs, fields, rates, cause, and
   expected downstream impact retained in a private-safe oracle.
7. **Independent oracle** — expected inventory, dispositions, quality
   outcomes, and campaign decision computed outside the code path being
   evaluated.
8. **Scale tiers** — a small committed fixture, a medium default nightly run,
   and an optional full ignored dataset with equivalent semantics.
9. **Privacy and license safety** — no real personal data; upstream origin,
   license, revision, and transformations recorded.
10. **Evidence honesty** — generated data is `fixture`; live DataHub behavior
    over that fixture is `live local`; neither becomes customer or production
    evidence.

## Failure-closed requirements

Every missing, stale, partial, ambiguous, contradictory, unlicensed,
unverified, or circular input prevents promotion. In particular:

- an acquisition mismatch refuses before use;
- incomplete graph paging blocks;
- metadata ingestion time cannot replace native data freshness;
- table-only lineage cannot become a field claim;
- ownership, glossary, tags, or a passing unrelated assertion cannot become
  native validation;
- a disappearing edge cannot close a consumer;
- a generator cannot edit the oracle after observation;
- a test using policy code to calculate expected policy output is invalid;
- a late consumer reopens readiness;
- public artifacts containing raw rows or sensitive paths are rejected.

## Benchmark scenarios and acceptance thresholds

The new Phase 06 benchmark must include at least these truth-labeled cases:

| Scenario | Expected safety result |
|---|---|
| exact compatible replacement and one validated dbt consumer | may reach `READY_TO_RETIRE` only inside its complete isolated envelope |
| rich graph with opaque non-repository consumers | `UNSAFE` |
| late downstream consumer | reopen to `UNSAFE` and refuse the producer action |
| incomplete lineage page | `BLOCKED` |
| stale underlying data with fresh ingestion timestamp | `BLOCKED` |
| table-only lineage for the legacy field | consumer remains unresolved or opaque |
| ambiguous native/DataHub identity | `BLOCKED` |
| incompatible type or unmapped status | `UNSAFE` before apply or native validation failure |
| null inflation or semantic parity failure | `UNSAFE` |
| quality failure on one healthcare branch | affected branch blocks; unrelated branch is not falsely failed |
| ownership without native validation | no closure |
| disappearing legacy edge without a receipt | no closure |

Acceptance requires:

- zero false `READY_TO_RETIRE` outcomes across the adversarial suite;
- exact expected decision and stable refusal code for every scenario;
- complete required-source paging or categorical refusal;
- 100% expected-consumer recall in the controlled truth graph;
- exact Git/dbt target equality and dbt-native semantic validation;
- deterministic twin-run data, oracle, manifest, and public artifact digests;
- direct DataHub reread of schemas, lineage, ownership, quality aspects, and
  published campaign context rather than trusting ingestion exit status;
- public artifacts free of raw source rows, secrets, and unstable local paths.

## Continuous execution protocol

The overnight objective is one large coherent replacement for the abandoned
Looker phase: implement and verify the DataHub evidence-quality benchmark end
to end. Do not stop after scaffolding, downloading a dataset, generating rows,
or passing one scenario.

### Checkpoint A — contract and surface reframe

- align `AGENTS.md`, `README.md`, `STATUS.md`, `PLAN.md`, product,
  architecture, contracts, requirements, risks, decisions, phases, access,
  compatibility, evaluation, and evidence documents;
- replace Phase 06 with the DataHub evidence-quality benchmark contract;
- label historical Looker evidence superseded without deleting truthful
  history;
- identify every Looker runtime, schema, CLI, recipe, fixture, test, and
  packaging reference to remove;
- commit and push the coherent documentation reframe.

### Checkpoint B — licensed dataset registry and reproducible acquisition

- add a versioned registry for official `fiction-retail`, `nyc-taxi`, and
  `healthcare` inputs pinned to an upstream commit and checksums;
- implement a no-surprise acquisition/preflight command with ignored cache,
  offline verification, license manifest, and actionable failures;
- prohibit unpinned network input during acceptance;
- add focused success, checksum mismatch, missing asset, and license tests;
- commit and push the dataset-boundary checkpoint.

### Checkpoint C — synthetic corpus and independent oracle

- build the deterministic fiction-retail field-replacement generator with
  small, medium, and full scale profiles;
- generate clean and adversarial variants with exact planted-fault manifests;
- implement the independent truth oracle and distribution/integrity checks;
- add the nyc-taxi freshness and healthcare branch-impact adapters without
  copying large source data into Git;
- inspect generated samples and twin-run digests;
- commit and push the corpus checkpoint.

### Checkpoint D — DataHub ingestion and evidence-quality evaluation

- ingest the benchmark into disposable DataHub Core using pinned tooling;
- emit and reread schemas, field/table lineage, owners, domains, glossary,
  tags, quality assertions or equivalent aspects, incidents where supported,
  and campaign documents;
- compare observed graph/evidence to the independent oracle;
- exercise complete, partial, stale, ambiguous, table-only, and contradictory
  evidence paths;
- ensure the existing campaign engine consumes the benchmark rather than a
  parallel evaluator;
- commit and push the DataHub benchmark checkpoint.

### Checkpoint E — full campaign, refusal matrix, and evidence promotion

- run the clean isolated Git/dbt path through apply, dbt validation,
  reconciliation, publication, and the harmless producer sentinel;
- run every adversarial scenario and inspect its refusal;
- generate schema-versioned public evidence with source revisions, modes,
  digests, limitations, recall, and false-readiness count;
- update `STATUS.md`, `docs/EVIDENCE_LEDGER.md`, `docs/RISKS.md`, and
  `docs/DECISIONS.md` from observed results;
- run all phase commands, `make check`, artifact/secret scans, package tests,
  and `git diff --check`;
- commit and push the verified Phase 06 replacement.

### Checkpoint F — remove the deprecated Looker release surface

- delete Looker runtime modules, CLI commands, deployment profiles, schema,
  recipes, live-access material, and package tests from the supported tree;
- retain only clearly labeled historical evidence or migration notes needed
  to explain old campaign records;
- verify existing non-Looker campaign replay, database migration, installed
  package, upgrade/rollback, and public artifact checks;
- commit and push the removal separately from benchmark behavior.

For every checkpoint: implement the smallest complete behavior, run focused
tests, inspect success and refusal artifacts, update status/evidence/risks and
decisions from observation, run the applicable broad checks, make a focused
commit, push it, and continue immediately.

## Work available before external access

All work in this goal is credential-independent. Public dataset acquisition,
synthetic generation, disposable DataHub Core, Git/dbt, DuckDB, packaging,
security, recovery, and evidence promotion can run without user access. Do not
report an external blocker for a missing command, tool, dataset cache, schema,
fixture, implementation, or local service; build or repair it.

Independent operator evidence may be recorded if another real operator becomes
available, but its absence does not serialize this engineering goal.

## Evidence contract

Every material result is one of:

- `live local` — observed against the running disposable DataHub Core, Git,
  dbt, or DuckDB boundary;
- `fixture` — deterministic official or generated data;
- `replay` — reproduced from a captured artifact;
- `analysis` — a conclusion that asserts no runtime behavior.

A live local run over fixture data proves integration behavior, not production
coverage or customer value. An official dataset is still fixture evidence.
Empty lineage, zero queries, an owner acknowledgment, an assertion pass, or a
disappearing edge never proves absence or closure by itself.

## Authority and repository boundary

The run may:

- modify this repository;
- start disposable local DataHub Core, Git, dbt, SQLite, and DuckDB resources;
- download public Apache-2.0, CC0, or public-domain inputs into ignored caches
  after revision and checksum verification;
- make focused commits and push the current branch to `origin`.

The run must not:

- access or provision Looker;
- mutate production or shared systems;
- commit large upstream databases, private data, credentials, raw query text,
  or generated local state;
- weaken live/fixture distinctions or acceptance thresholds;
- replace native validation with generated expectations;
- force-push, rewrite history, or discard unrelated user changes.

## External boundary protocol

No external system boundary is currently required. If an unexpected boundary
appears, first prove it through safe preflight, finish every independent task,
name the smallest least-privileged input, generate a no-secret request, and
preserve an exact resume command. Never convert an implementation problem into
an access request.

## Reframe protocol

Edit this goal and align the repository if direct evidence invalidates a
central assumption—for example, the official assets cannot be licensed or
reproduced, the independent oracle cannot remain independent, DataHub cannot
represent the controlled truth graph, or the benchmark does not exercise the
real campaign engine. Record the failed experiment, mode, artifacts,
requirements, risks, decision, and narrower defensible claim. Do not conceal a
failed thesis with more data volume or another integration.

## Completion states

### Complete

The goal is complete only when:

- Looker is absent from the supported product, package, active contracts,
  commands, and acceptance requirements;
- the new Phase 06 benchmark passes against pinned official datasets and the
  deterministic synthetic corpus;
- every benchmark scenario has inspected truth, observed evidence, expected
  decision, and stable refusal output;
- the isolated campaign reaches `READY_TO_RETIRE` and the adversarial/rich
  campaigns refuse without false readiness;
- DataHub Core, MCP/API, Git/dbt, reconciliation, publication, reports, and
  producer gate use one campaign engine and canonical manifest;
- security, fault, recovery, install, package, upgrade, and reference checks
  pass after Looker removal;
- documentation, schemas, package contents, status, requirements, risks,
  decisions, and evidence agree;
- focused commits are pushed and the remote commit is verified.

Independent operator adoption remains valuable follow-on evidence, but it is
not a reason to retain Looker and does not block completion of this overnight
engineering goal. Do not manufacture an operator result.

### Reframed

Use only if observed evidence triggers the reframe protocol and implementation,
contracts, status, and evidence all describe the narrower result.

### Blocked

Use only after the same genuine external boundary repeats under the strict
Codex goal protocol and no safe work remains. Current missing benchmark
implementation is not a blocker.

## Final handoff

Report:

- final commit and remote verification;
- official inputs, upstream revisions, licenses, and checksums used;
- synthetic generator version, seed, scale, quality checks, and oracle digest;
- live local systems exercised;
- successful campaign and every refusal scenario;
- public artifact paths and digests;
- Looker files and interfaces removed;
- remaining limitations and adoption evidence still not observed.
