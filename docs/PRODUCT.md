# Product definition

## One sentence

Retirement Conductor moves known consumers off a legacy data field, verifies
the changes in each consumer's native environment, and prevents retirement
until the declared evidence is fresh and every in-scope consumer has an
acceptable disposition.

## The human story

A data platform team wants to replace `orders.legacy_status` with
`orders.order_status`. The producing team can change the warehouse quickly,
but nobody has a trustworthy answer to four questions:

1. Which pipelines, models, dashboards, reports, and ad hoc workloads still
   rely on the old field?
2. Which of those can be changed safely and by whom?
3. Did each changed consumer still work afterward?
4. Did anything new appear between the original inventory and the final
   producer change?

Today those answers are split across catalogs, repositories, query logs,
platform-specific validators, tickets, and human memory. Retirement Conductor
makes them one executable campaign.

## User and buyer

Primary operator:

- a data platform or analytics infrastructure engineer responsible for schema
  evolution across multiple consumer systems.

Primary beneficiary:

- consumer owners who receive a concrete change or a precisely scoped action,
  rather than a vague blast-radius notification.

Likely buyer:

- the leader accountable for data-platform reliability, migration throughput,
  and the cost of coordinating breaking changes.

Best-fit environment:

- DataHub is already connected to more than one data system;
- important transformations live in Git;
- BI or other non-repository consumers exist and must remain visible even when
  the product cannot mutate them;
- schema changes are frequent or costly enough to justify a repeatable control
  plane.

An organization with one repository, one warehouse, and no external consumers
may be better served by dbt and ordinary review automation.

## Job to be done

> When an important data field must be replaced, help me move the known
> consumers safely, identify what cannot be proven, and give the producing
> team an evidence-backed decision it can enforce.

## Product category

Retirement Conductor is verified change operations for the data stack,
expressed through one complete workflow: column replacement and retirement.

It is not:

- another catalog or lineage graph;
- a downstream-impact report;
- a deprecation flag;
- a generic coding assistant;
- a bulk text replacement service;
- an issue tracker with an agent attached;
- a universal guarantee that hidden consumers do not exist.

## The durable product artifact

The central artifact is a versioned campaign manifest containing:

- the exact legacy and replacement identities;
- the declared evidence envelope;
- baseline and reconciliation graph snapshots;
- every in-scope consumer and its native identity;
- source versions and before/after fingerprints;
- authorized target sets;
- native validation receipts;
- unresolved, opaque, stale, failed, removed, or waived dispositions;
- policy version and deterministic decision;
- a stable summary written to and read back from DataHub.

The manifest is useful because it corresponds to changed and validated state,
not because it is a polished report.

## Product promise and non-claims

Promise:

> All consumers observed through the declared sources have been accounted for
> under the recorded policy, or the retirement action is refused.

Non-claims:

- that every consumer in the company is observable;
- that metadata freshness is the same as source freshness;
- that owner approval proves semantic equivalence;
- that a native validator proves every business meaning;
- that a hash proves authorship;
- that DataHub alone can safely mutate every connected platform;
- that readiness is permanent before the producer action commits.

## The complete first path

```text
warehouse column A → compatible warehouse column B

DataHub inventory
  + configured Git/dbt repository
  + dbt-native validation
  + fresh DataHub reconciliation
  + stable DataHub summary
  + fresh check-and-retire command
```

This is one complete product outcome. It does not depend on support for every
consumer platform.

There is no required second native mutation path. Instead, a reproducible
DataHub evidence-quality benchmark proves that the conductor handles rich,
late, stale, partial, ambiguous, table-only, and quality-failing context
without creating false readiness. Git/dbt remains the sole supported
production-shaped automated consumer executor.

The consequential reference path adds a separately privileged, loopback-only
PostgreSQL producer action after the consumer campaign closes. It records
one-use intent before obtaining the mutation client, executes one exact
allowlisted `DROP COLUMN` without `CASCADE`, rereads the native schema, and
retains `OUTCOME_UNKNOWN` authority until an explicit native reread resolves
the result. This proves the producer boundary without claiming production
warehouse support.

## Definitive comparison and simplification

The frozen CP-03 comparison and the live native action agree on
`NO_MATERIAL_ADVANTAGE` / `SIMPLIFY`. Retirement Conductor and competent fresh
CI both refused the identical late-consumer intervention with equivalent
action-time DataHub, Git/dbt, Superset, approval, producer-schema,
publication, and outcome evidence. The point-in-time static arm committed and
caused the independent Spark legacy workload to fail with SQLSTATE `42703`.

The product claim is therefore simpler: fresh, failure-closed verification is
the safety requirement. The default producer command now prepares its binding,
rereads every required source, records durable intent, and executes or refuses
inside one trusted invocation. The internal plan and ledger preserve recovery
and audit evidence without making an operator carry a separate lease. The old
two-step plan/gate surface and watcher remain advanced compatibility tools for
demonstrated handoff needs; they are not a material safety advantage over
competent fresh CI for the bounded case.

## Agent and advisory surfaces

Codex can operate the same campaign engine through a project-scoped MCP server
and repository skill. The model selects bounded operations and explains
results; it cannot record approval, accept native validation, alter policy, or
override the producer gate. Sixteen MCP tools cover campaign inspection,
Git/dbt planning and execution, publication, optional lease status, one-shot
fresh observation, and the separately confirmed compatibility gate. The
privileged PostgreSQL `producer retire` command remains outside the browser,
skill, and general agent credential boundary.

Planning retains bounded DataHub schema, lineage, glossary, query, quality,
ownership, and freshness context, but nested model selection is not part of
the supported product. A 135-attempt ablation found that the richer context
improved safety-critical fault coverage while the nested Gemini planner failed
the predeclared minimum-plan and operator-value thresholds. Deterministic code
selects and validates supported checks; reviewed templates materialize them.

The project skill and product MCP remain the primary Codex operating surface
because a separate 72-run ablation improved correct completion and reduced
calls and retries. This is an operational result for the recorded host and
model, not capability containment: shell, file editing, and mutation-capable
DataHub tools remained exposed in every tested condition.

A bounded Superset executor has passed a disposable campaign-integration
experiment. It now uses canonical campaign state, digest-bound approval,
consumer receipts, reconciliation, deterministic readiness, compensation, and
an operator CLI. One live campaign accepted both Git/dbt and Superset receipts,
became `READY_TO_RETIRE`, and returned to `UNSAFE` when the Superset change was
restored. The final producer gate now authenticates a distinct read/execute-only
principal, rereads exact database/dataset/chart identities and SQL, forces
saved-chart execution, and rejects native drift before producer mutation. It
remains live-local experimental scope: additional dialects, production
credentials, and independent operator need have not been observed.

## Build, borrow, and delegate

Build:

- campaign state and deterministic policy;
- evidence envelopes and provenance-aware receipts;
- adapter orchestration and identity binding;
- source-version, scope, and authorization preconditions;
- reconciliation and a fresh producer-side action or refusal;
- shared operator view and DataHub summary.

Borrow:

- DataHub search, lineage, ownership, schema, query, document, and event
  surfaces;
- Git branches and review;
- dbt parse, build, and tests;
- source platform authentication and audit logs.

Delegate:

- source-specific code generation to the most capable authorized tool;
- semantic judgment to declared validators and accountable reviewers;
- final destructive producer action to a separately privileged process.

## What makes it defensible

Any one component can be copied. The defensible system is the protocol and
operational history that make unrelated components satisfy one continuously
reconciled completion criterion:

- fresh source-native evidence rather than confidence labels;
- exact identity mapping across DataHub and native objects;
- failure-closed transitions under graph and source drift;
- explicit blind spots instead of false completeness;
- a concrete Git/dbt boundary that preserves native validation;
- one privileged final command that can perform or prevent the producing
  change from fresh evidence.

This becomes shallow if it only inventories, reports, scores, notifies, or
stores receipts without changing and reconciling consumer state.

## Success measures

Product behavior:

- share of inventoried consumers with source-native identities;
- share closed by `VALIDATED`, `REMOVED`, or proved `NOT_APPLICABLE`;
- stale or newly observed consumers caught before producer change;
- campaigns resumed deterministically after interruption;
- false readiness events, which must remain zero in controlled tests;
- median operator interventions per closed consumer;
- evidence recall and false-readiness rate against a controlled truth graph.

Customer value:

- consumer migrations completed without post-change breakage;
- reduction in manual inventory and coordination work;
- reduction in time spent proving whether a change may proceed;
- number of planned retirements completed rather than left indefinitely
  deprecated.

These measures require real operational observation; repository activity alone
does not prove value.

## Reasons to stop or reframe

Reframe the product if evidence shows any of the following:

- DataHub does not materially expand or improve the actionable consumer set;
- the Git/dbt mutation and DataHub reconciliation loop cannot preserve one
  coherent evidence and receipt contract;
- native validation is unavailable for the systems customers care about;
- the producer-side gate cannot be integrated into real change workflows;
- most closures collapse into unverifiable acknowledgments;
- target customers perform this operation too rarely to support a product;
- a current platform demonstrably supplies the same cross-system execution,
  native validation, reconciliation, and refusal loop.
