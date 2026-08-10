# Architecture

## Architectural thesis

Retirement Conductor is a small deterministic control plane around existing
systems of record. It does not become the source of truth for warehouse
schemas, Git content, BI objects, or the metadata graph.

```text
                        ┌──────────────────────┐
                        │ Retirement spec      │
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │ Campaign engine      │
                        │ deterministic policy │
                        └──────┬────────┬──────┘
                               │        │
                 evidence read │        │ authorized action
                               │        │
              ┌────────────────▼─┐   ┌──▼──────────────────┐
              │ DataHub boundary │   │ Git/dbt boundary    │
              │ graph + context  │   │ guarded + validated │
              └────────┬─────────┘   └─────────┬───────────┘
                       │              ┌─────────▼───────────┐
                       │              │ Superset boundary  │
                       │              │ experimental       │
                       │              └─────────┬───────────┘
                       └──────────┬─────────────┘
                                  │ receipts
                       ┌──────────▼───────────┐
                       │ Campaign store       │
                       │ events + snapshots   │
                       └──────────┬───────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
          ┌─────────▼──────────┐      ┌─────────▼──────────┐
          │ DataHub summary    │      │ Report + CI gate   │
          │ agent-readable     │      │ same policy output │
          └────────────────────┘      └────────────────────┘
```

## Authority boundaries

| Concern | Authority | Retirement Conductor responsibility |
|---|---|---|
| Warehouse and schema identity | Warehouse plus DataHub-ingested metadata | Resolve both identities and record mapping evidence |
| Cross-system inventory | DataHub within declared scope | Page completely, record freshness and blind spots, normalize consumers |
| Repository content | Git commit and working tree | Hash, branch, patch only allowed files, preserve reviewability |
| dbt validity | dbt runtime and project tests | Invoke exact commands and capture redacted results |
| Non-repository consumers | Their native systems plus DataHub-ingested metadata | Retain exact observed identity and evidence; require an external receipt, verified removal, or proved non-applicability rather than pretend to mutate them |
| Campaign transitions | Deterministic policy engine | Own the state machine and refusal decision |
| In-progress campaign state | Local durable campaign store | Persist events, attempts, snapshots, receipts, and policy version |
| Shared campaign context | DataHub document or supported metadata surface | Publish stable summary and verify agent-visible read-back |
| Final producer mutation | Separately privileged producer workflow | Supply an enforceable gate result, not broad warehouse credentials |

DataHub summaries are durable shared context, but they are not used as a
transaction log. Metadata ingestion and indexing are eventually consistent,
and document mutation alone does not provide the compare-and-swap semantics
needed for campaign execution.

## Initial runtime shape

One Python command-line process with:

- a pure campaign-policy module;
- typed domain models;
- a SQLite database using the standard library;
- file-backed redacted artifacts;
- a DataHub client boundary;
- one Git/dbt adapter;
- deterministic JSON manifests;
- generated HTML and terminal views from the same manifest.

This shape is enough to complete and resume one campaign, test failure modes,
and integrate into producer CI. It avoids service orchestration before there is
a demonstrated multi-user or scale requirement.

The supported deployment is explicitly single-writer. One deployment identity
owns the SQLite state directory and local campaign lock. A copied database,
second runner, or network-shared filesystem is not treated as coordinated
state. The store binds both writer identity and resolved path, checks an
existing binding read-only before changing SQLite journal state, and refuses
known shared filesystem types. This is local authority, not distributed
consensus.

## Components

### Specification loader

Parses and validates:

- target and replacement identities;
- evidence sources and whether each is required;
- traversal and repository scope;
- allowed native objects and files;
- validation commands;
- approval references;
- policy version.

It resolves secrets by reference at runtime. Secrets never enter the
specification or campaign manifest.

### Campaign engine

The engine:

- evaluates legal state transitions;
- freezes inventory and policy snapshots;
- rejects missing or stale evidence;
- dispatches only explicitly authorized adapters;
- accepts receipts only after strict validation;
- requires fresh reconciliation before readiness;
- returns stable refusal codes;
- generates one canonical manifest.

The engine is deterministic for identical inputs. Model output cannot directly
change campaign state.

### Campaign store

SQLite stores append-oriented campaign events and materialized current state:

- campaign and attempt identifiers;
- specification and policy digests;
- baseline and reconciliation snapshots;
- consumer identities and dispositions;
- adapter plans and receipts;
- approvals and their scope;
- state transitions and refusal codes.

Raw artifacts remain on disk and are addressed by digest. The database stores
references and safe summaries, not credentials or unrestricted query text.

The store supports non-overwriting online backups under its write lock. A
backup is published only after SQLite integrity and foreign-key checks,
canonical event replay, manifest and gate-ledger validation, and exact logical
snapshot comparison. Restore is supported only to the original bound path.
Operational diagnostics validate the same logical state before emitting
aggregate counts, digested campaign identities, stuck or stale campaigns,
repeated refusals, and unresolved gate activity.

The first implementation does not introduce a generic storage abstraction.
Extract one only when a second store is genuinely required.

### DataHub boundary

Read path:

- inspect the live capability surface;
- resolve canonical entities from search;
- retrieve schema, owners, multi-hop lineage, lineage paths, and permitted
  query context;
- page to termination using the strongest live API surface;
- request the native lineage cache bypass, retain the request and response,
  and mark the source partial if it reports that cached data was used;
- retain response counts, truncation indicators, source freshness, and errors.

Write path:

- publish a stable campaign summary only after policy evaluation;
- update the same logical record idempotently;
- read it back through an agent-visible surface with bounded read-only polling,
  without repeating the write;
- mutate lifecycle state only through a separately authorized action after
  readiness.

The boundary must distinguish DataHub Core and DataHub Cloud capabilities at
runtime rather than assume the union of their documentation.

### Git/dbt execution boundary

The sole fully producer-gated executor maps a DataHub consumer to an exact Git/dbt native
identity and implements:

```text
preflight
  → discover identity
  → snapshot
  → plan
  → apply
  → validate
  → compensate
  → emit receipt
```

The executor never decides campaign readiness. It returns evidence or a stable
refusal.

Native execution treats repositories, project code, macros, hooks, generated
content, and API responses as untrusted input. Validators run with disposable
credentials and bounded filesystem, subprocess, environment, and network
access appropriate to the supported source. Path and symlink resolution must
remain inside the approved root.

### Experimental Superset execution boundary

The loopback-only Superset boundary maps one DataHub connector URL to exact
dataset, database, and chart UUIDs. It replaces one executable unquoted SQL
identifier under an explicit dataset allowlist, forces saved-chart execution,
compares safe semantic output, emits the common consumer receipt, and supports
fingerprint-safe compensation. `SupersetCampaignWorkflow` binds those records
to the same durable campaign transitions as Git/dbt, including multiple exact
native identity claims in one campaign.

This is not yet a second complete producer-gated path. Campaign reconciliation
and readiness accept the receipt, but the final gate still independently
refreshes only DataHub and Git/dbt. Until a gate-time Superset reread lands, the
extension remains experimental and cannot grant producer action authority.

### Context-aware deterministic planner

The supported planner consumes bounded DataHub and dbt evidence as data:

- exact schema and field identities;
- field and table lineage with their granularity kept distinct;
- glossary, query, quality, ownership, and freshness signals with explicit
  absence and limitations;
- exact repository, manifest, file, validator, and supported-check identities.

Deterministic code selects only the supported safe primitives, binds their
evidence, and materializes reviewed templates. It verifies file scope, content
versions, target identity, and validator results. The removed nested
Vertex/Gemini transport remains represented only by historical experiment
artifacts and does not participate in the packaged or canonical run.

Codex may still interpret this context, choose campaign operations, and
explain results through the retained skill and product MCP. Its output is not
authorization, native validation, or policy input.

### Agent interface

The project-scoped STDIO MCP server is an adapter over the existing CLI
dispatcher, not another campaign engine. Codex and the repository skill can
inspect context, choose operations, and explain refusals. The server has no
authorization-recording tool. Human approval remains an out-of-agent durable
record, and every mutation or gate call still passes through deterministic
preconditions.

The interface is authority-contained by those deterministic preconditions,
not by the host capability surface. Recorded Codex environments exposed shell
and file editing, and the DataHub MCP advertised metadata mutations. Tool
non-use is behavioral evidence only; the architecture makes no
capability-bounded claim.

### Reconciler

The reconciler:

1. refreshes the relevant metadata source when supported;
2. obtains equivalent legacy-field and replacement-field graph snapshots;
3. rereads every accepted native source and reruns its validator;
4. compares source identities, immutable object identity, and membership;
5. invalidates only the receipt whose native or exact legacy-edge evidence
   drifted;
6. adds newly observed consumers as blockers; and
7. records table-only or vanished edges without treating disappearance alone
   as validation.

An edge disappearing is only one signal. A consumer closes through a valid
native receipt, verified removal, or proved non-applicability under policy.
An exact replacement field edge can corroborate a native Git/dbt receipt;
table-only lineage is recorded explicitly and never upgraded into a field
claim. A non-repository consumer never closes from graph change alone.

### Retirement Lease watcher

The one-shot watcher is optional coordination infrastructure over an issued
producer plan. Competent fresh action-time CI matched its bounded safety result
in the definitive comparison, so the architecture does not require a
long-lived lease service where the same checks can run immediately before a
one-shot action. Under the
campaign store's existing operation lock it records a no-authority observation
event, resumes or performs fresh reconciliation, republishes the canonical
summary, verifies read-back, and emits a digest-bound watch receipt with a
stable result and exit code. Any observation changes the canonical manifest
and therefore invalidates the observed lease, even if the campaign remains
ready. A later gate requires a newly issued lease.

The watcher is cron-safe and interruption-resumable for one local writer. It
does not create a scheduler, distributed service, or durable authorization.

### Operator views and gate

The command line and generated report consume the canonical manifest. They do
not reimplement policy. Before rendering, they validate the manifest schema
and canonical digest, then reduce it through one shared presentation model.
That model exposes:

- target, replacement, decision, counts, evidence coverage, and next action;
- each source's mode, scope, freshness, pagination, permissions, versions, and
  limitations;
- each consumer's disposition, native action, receipt digest, and current
  receipt acceptance state;
- stable blocker or review code, evidence source, and safe recovery action;
- canonical transition and DataHub publication history.

The concise terminal view, expanded explanation, local HTML report, and
structurally redacted public report all render this model. The Retirement
Workbench adds a second, deliberately narrower projection for one selected
campaign: current decision, exact cause, campaign stage, focused lineage,
and one next action. Its Consumers, Change, Evidence, and Activity views reveal
supporting proof one category at a time. The Workbench validates the same
manifest and requires its event digests to exactly match canonical transition
history; it never evaluates policy in the browser.

The Workbench API is a loopback-only, single-campaign adapter over the same
path-bound store and command runtime. Reads are always available. Inventory
and reconciliation are disabled unless the operator starts the server with an
explicit action flag, and requests require an exact action header from an
allowlisted browser origin plus a process-scoped bearer token. The hosted page
loads recorded evidence by default and can explicitly pair to this loopback
adapter; DataHub credentials, the campaign store, and operation execution
remain local. The browser cannot record authorization, apply a Git/dbt plan,
issue a Retirement Lease, or execute the producer gate. This is a local
operator surface, not the shared multi-operator API service deferred below.

Public rendering
removes native identities and sensitive source detail before HTML generation;
it is not a post-processing scrub. Reports are deterministic, self-contained,
and non-authoritative: the verified private manifest remains the integrity
source, and a report or digest is never apply or gate authorization.

Native planning and mutation stay distinct. Apply requires both the durable
approval for the current plan and an exact operator-confirmed plan digest.
Neither confirmation nor presentation can expand the plan's authorized target
set.

The default producer-side invocation:

- reloads current campaign state;
- requires a fresh reconciliation within policy;
- verifies manifest and receipt digests;
- rereads DataHub, Git/dbt, Superset native identity/SQL/forced execution,
  producer source and schema, validators, authorization, and publication
  bindings immediately before action;
- internally issues a short-lived plan for the exact canonical manifest in the
  same trusted invocation; operators do not need to carry a lease;
- records durable intent before the producer action and records its outcome;
- exits zero only for `READY_TO_RETIRE`;
- consumes the manifest and internal plan binding so a prior green result cannot be
  replayed or recomputed into another authorization;
- rejects a known consumed plan before repeating external checks, while an
  atomic later claim closes concurrent attempts;
- obtains a separately privileged PostgreSQL mutation client only after
  durable intent and classifies lost responses by native schema reread; and
- does not itself hold general mutation credentials.

The older two-step `producer plan` and `gate` commands expose the same internal
artifacts for compatibility and explicit recovery. The optional watcher can
observe and invalidate such issued plans. Neither is required by the default
fresh check-and-retire path.

## Consistency and concurrency

Retirement touches systems without a shared transaction. The product therefore
uses a saga with explicit preconditions:

- pin baseline graph and source versions;
- acquire a campaign-scoped local write lock;
- compare source fingerprints immediately before apply;
- record intended targets before mutation;
- compare actual targets after mutation;
- treat a lost response as outcome unknown and reread native state before
  retry;
- compensate only when the current native fingerprint still matches the
  expected post-apply state;
- reconcile all evidence again;
- invalidate readiness if target, replacement, policy, configuration,
  authorization, validation, or graph state changes before the producer
  action.

Overlapping campaigns may target the same consumer. The first implementation
detects this by native identity and refuses concurrent apply. It does not
attempt distributed lock management.

## Receipt integrity and provenance

Canonical JSON plus SHA-256 supplies deterministic content identity and change
detection. It does not establish authorship. Each receipt therefore also
records:

- adapter and validator version;
- native principal or safe principal identifier;
- source system request or run identifier when available;
- Git commit and CI run identity where applicable;
- captured time and evidence artifact references.

Cryptographic signing is deferred until the deployment threat model identifies
the signer, key custody, verification boundary, and recovery process.

## Failure policy

Expected failures are domain results:

- source not found;
- identity ambiguous;
- evidence incomplete;
- pagination incomplete;
- permission insufficient;
- source stale;
- target scope expanded;
- replacement invalid;
- apply partially failed;
- validation failed;
- compensation failed;
- graph changed;
- receipt expired;
- approval missing.

Each maps to a stable refusal code, retained evidence, and a safe next action.
Unexpected exceptions never promote state.

## Evolution rule

Only expand the architecture when evidence requires it:

- introduce an API service when more than one operator must share active state;
- introduce a worker when native operations cannot safely remain synchronous;
- introduce another database when SQLite limits a demonstrated deployment;
- introduce an adapter SDK only after a real operator supplies a second native
  requirement and disposable evidence demonstrates genuinely shared semantics;
- introduce event-driven rescan after the explicit reconciliation loop is
  proven correct.
