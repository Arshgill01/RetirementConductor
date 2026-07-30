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
              │ DataHub boundary │   │ Native adapters     │
              │ graph + context  │   │ Git/dbt, then Looker│
              └────────┬─────────┘   └─────────┬───────────┘
                       │                       │
                       └──────────┬────────────┘
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
| Looker content | Looker API and content model | Map native identity, mutate bounded objects, invoke native validation |
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

The first implementation does not introduce a generic storage abstraction.
Extract one only when a second store is genuinely required.

### DataHub boundary

Read path:

- inspect the live capability surface;
- resolve canonical entities from search;
- retrieve schema, owners, multi-hop lineage, lineage paths, and permitted
  query context;
- page to termination using the strongest live API surface;
- retain response counts, truncation indicators, source freshness, and errors.

Write path:

- publish a stable campaign summary only after policy evaluation;
- update the same logical record idempotently;
- read it back through an agent-visible surface;
- mutate lifecycle state only through a separately authorized action after
  readiness.

The adapter must distinguish DataHub Core and DataHub Cloud capabilities at
runtime rather than assume the union of their documentation.

### Native adapter

An adapter owns one source domain. It maps a DataHub consumer to an exact
native identity and implements:

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

The adapter never decides campaign readiness. It returns evidence or a stable
refusal.

### Model-assisted planner

Model assistance is optional and constrained to:

- explaining consumers and candidate mappings;
- proposing minimal source changes;
- highlighting aliases, templates, and indirect references;
- generating operator summaries.

Every proposal is data, not authority. Deterministic boundaries verify file
scope, content versions, target identity, and validator results.

### Reconciler

The reconciler:

1. refreshes the relevant metadata source when supported;
2. obtains a new graph snapshot;
3. compares source identities and consumer membership;
4. invalidates stale receipts;
5. adds newly observed consumers as blockers;
6. records vanished edges without treating disappearance alone as validation.

An edge disappearing is only one signal. A consumer closes through a valid
native receipt, verified removal, or proved non-applicability under policy.

### Operator views and gate

The command line and generated report consume the canonical manifest. They do
not reimplement policy.

The producer-side gate:

- reloads current campaign state;
- requires a fresh reconciliation within policy;
- verifies manifest and receipt digests;
- exits zero only for `READY_TO_RETIRE`;
- records the exact policy decision;
- does not itself hold general mutation credentials.

## Consistency and concurrency

Retirement touches systems without a shared transaction. The product therefore
uses a saga with explicit preconditions:

- pin baseline graph and source versions;
- acquire a campaign-scoped local write lock;
- compare source fingerprints immediately before apply;
- record intended targets before mutation;
- compare actual targets after mutation;
- compensate when safe after partial failure;
- reconcile all evidence again;
- invalidate readiness if state changes before the producer action.

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
- introduce an adapter SDK after the Git/dbt and Looker implementations reveal
  genuinely shared semantics;
- introduce event-driven rescan after the explicit reconciliation loop is
  proven correct.
