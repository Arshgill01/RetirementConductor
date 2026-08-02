# Scope pressure pass

The build fails in two opposite ways: it can be too shallow to constitute a
product, or too elaborate to finish and operate. This pass defines the line.

## Underengineering traps

### Stopping at inventory

Symptom: the system lists consumers and owners but does not change or validate
anything.

Required correction: one real source change, native validator receipt, fresh
reconciliation, and gate outcome.

### Treating a patch as completion

Symptom: a model proposes a diff and the campaign marks the consumer migrated.

Required correction: source fingerprint, authorized target set, actual apply,
and source-native validation.

### Treating graph disappearance as success

Symptom: a consumer edge disappears after ingestion and closes automatically.

Required correction: retain the consumer until a valid native receipt,
verified removal, or proved non-applicability exists.

### Persisting only a report

Symptom: HTML or Markdown is the campaign state.

Required correction: durable event and snapshot state; views render the
canonical manifest.

### Producing advice rather than enforcement

Symptom: the system recommends waiting but the producer change can proceed
unchanged.

Required correction: a non-zero producer-side gate invoked by a representative
change workflow.

### Hiding unknowns

Symptom: empty query history or incomplete lineage lowers confidence but still
permits readiness.

Required correction: required-source status is categorical and failure-closed.

## Overengineering traps

### Supporting every asset immediately

Tables, metrics, datasets, APIs, pipelines, and infrastructure have different
identity and validation semantics.

Control: finish compatible column replacement first.

### Building a distributed platform before one complete local campaign

Queues, workers, service discovery, and operational databases add failure modes
without proving product value.

Control: one command-line process and SQLite.

### Designing a universal adapter SDK from imagination

The wrong abstraction can force every platform into fake uniformity.

Control: keep the Git/dbt boundary concrete. Extract reusable native-executor
code only after a real second requirement and disposable evidence exist.

### Rebuilding native intelligence

A custom SQL transpiler, dbt compiler, BI validator, or metadata graph
would compete with stronger domain tools.

Control: orchestrate native tools and normalize evidence.

### Building the interface before the engine

A polished control room can conceal static or fixture state.

Control: operator views consume only canonical engine artifacts.

### Premature cryptography

Signing receipts without a signer and key-management model adds ceremony, not
trust.

Control: deterministic digests plus native provenance first.

### General workflow and ticket integrations

Notifications and approvals are useful but easy to overbuild and already
available in surrounding platforms.

Control: expose stable owner actions and events; add one real integration only
when a user workflow demands it.

## The balanced product shape

Build deeply:

- exact identity;
- evidence coverage;
- deterministic policy;
- guarded source changes;
- native validation;
- reconciliation;
- recovery;
- producer enforcement.

Build narrowly:

- one asset type;
- one replacement shape;
- one source repository;
- one native Git/dbt executor plus one rigorous DataHub evidence benchmark;
- one portable command-line runtime;
- one shared DataHub summary.

## Expansion gates

Add a new asset type only when:

- its identity model is documented;
- its validator can produce meaningful evidence;
- its retirement semantics fit or explicitly extend the campaign contract;
- one real user workflow requires it.

Add a new adapter only when:

- a consequential unresolved consumer uses that platform;
- a supported, bounded mutation exists;
- source versioning and native validation exist;
- apply and recovery can be tested safely.

Add a service runtime only when:

- multiple operators must share active state;
- a native operation requires asynchronous execution;
- deployment evidence shows the command-line shape is insufficient.

Add an approval system only when:

- the existing source, Git, or DataHub workflow cannot express the required
  authority;
- the approval can be bound to an exact plan and source version.

## Final scope decision

The repository plans the complete product, but the implementation sequence
must preserve one rule:

> Complete one consequential retirement end to end before increasing breadth.
