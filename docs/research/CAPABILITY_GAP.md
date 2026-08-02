# Capability and gap pass

This map asks two different questions:

1. What does DataHub already provide?
2. What must Retirement Conductor contribute for the workflow to be a product?

It reflects public documentation and open-source code reviewed on 2026-07-30.
It does not claim visibility into private implementations.

## DataHub capabilities we should use

### Cross-system context

DataHub supplies:

- table- and column-level lineage with multi-hop impact analysis;
- schema, ownership, domains, glossary, documentation, and quality context;
- usage and observed query context where connectors provide it;
- search and exact entity retrieval;
- an MCP surface for agent access;
- GraphQL and SDK surfaces for deeper or missing operations.

These are the inventory foundation. Rebuilding them would make the product
worse and harder to maintain.

### Lifecycle and shared metadata

DataHub supplies:

- dataset deprecation metadata and GraphQL mutations;
- context documents and metadata mutation surfaces;
- incidents with their own active/resolved lifecycle;
- producer-oriented data contracts made of verifiable assertions;
- Cloud change proposals for governed metadata suggestions;
- workflow and event primitives in supported editions;
- actions and events that can drive external automation.

These capabilities can host summaries, ownership actions, notifications, and
later workflow integration. They do not need a parallel implementation in
Retirement Conductor.

### Existing agent guidance

The official DataHub skills cover search, lineage analysis, and metadata
enrichment including deprecation. Public skill content does not define an
evidence-scoped retirement campaign that changes native consumers and accepts
source-native receipts.

## Source-native capabilities we should delegate to

### Git and dbt

Git supplies immutable commits, reviewable branches, and audit history. dbt
supplies project parsing, compiled state, lineage, contracts, tests, and native
execution. dbt Wizard can propose coordinated, validated dbt changes.

Retirement Conductor should enforce campaign scope and consume the resulting
evidence. It should not compete to become a dbt compiler or the most capable
dbt coding agent.

### Non-repository consumers

BI, notebook, pipeline, and model platforms remain authoritative for their
objects. The current product does not automate them. DataHub evidence keeps
them in the campaign, and closure requires a validated external receipt,
verified removal, or proved non-applicability rather than an inferred catalog
state.

## Missing cross-system capability

The reviewed public surfaces do not clearly provide one product that:

1. declares a bounded field retirement;
2. inventories consumers across DataHub and named non-catalog sources;
3. maps each graph consumer to an exact native object;
4. dispatches the authorized Git/dbt source-native change;
5. accepts only fresh native validation receipts;
6. maintains one durable per-consumer closure state;
7. reconciles the graph again and invalidates stale evidence;
8. refuses the producer change until every observed consumer has an acceptable
   evidence-backed disposition;
9. publishes the result back into DataHub for the next operator or agent.

This is the gap Retirement Conductor must fill.

## The gap that is not enough

None of these alone justifies a product:

- a richer lineage screen;
- a list of owners;
- a deprecation notice;
- generated SQL changes;
- a collection of validation logs;
- a dashboard showing completion percentages;
- notifications and approval forms;
- a final receipt without source mutation.

Each is either already available, easily composed, or a feature inside the
larger loop.

## DataHub integration boundary

Use runtime capability inspection because documented DataHub Cloud, DataHub
Core, MCP, GraphQL, and skill surfaces do not always expose identical
operations.

The initial product must:

- support the self-hosted MCP read path;
- use GraphQL or SDK where complete pagination or a required mutation is not
  exposed by the live MCP server;
- name capability fallbacks in evidence;
- never present a Cloud-only workflow as a Core feature;
- fail explicitly when a required surface is unavailable.

## Official benchmark opportunity

The hackathon resource page supplies three useful truth-bearing datasets that
the repository did not previously exercise: fiction-retail for a clean
relational field replacement, nyc-taxi for native freshness gaps invisible in
metadata timestamps, and healthcare for deterministic quality failures across
a forked graph. The benchmark should combine them with an independent oracle
rather than add another proprietary integration.

## Opportunity for upstream work

If implementation confirms the prior MCP pagination or deterministic document
creation limitations, the smallest useful upstream changes are:

- correct lineage pagination semantics and tests;
- clearer completeness and truncation metadata;
- a documented stable create-or-update document path;
- a DataHub skill that inventories retirement evidence without claiming
  completion;
- documentation that distinguishes impact analysis from validated closure.

Upstream work should improve the shared primitive, not move the entire product
into DataHub.
