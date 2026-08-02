# Competitive boundary pass

## Responsible conclusion

Retirement Conductor is not entering an empty market. The strongest defensible
claim is:

> In the current primary public documentation reviewed, no single product
> clearly combines DataHub-bounded field impact, guarded Git/dbt mutation,
> native semantic validation, fresh graph reconciliation, and a deterministic
> producer-side refusal gate with an explicit evidence-quality envelope.

This is a qualified observation, not proof that no company or internal system
has implemented the workflow.

## Closest products

### DataHub

Strong at cross-system metadata, lineage, impact analysis, ownership, query
context, deprecation metadata, documents, contracts, incidents, agent context,
and event-driven extension. It is the foundation and a potential platform
competitor if it adds native execution and closure workflows.

Current documented gap relevant to this product: stock impact and enrichment
surfaces do not visibly migrate each native consumer, accept its validator
receipt, reconcile all systems, and gate the producer action.

### Atlan

The closest lifecycle thesis competitor. Its MCP lifecycle workflow documents
downstream-consumer inspection, ownership, communication, migration
prioritization, and marking assets deprecated.

Current documented gap relevant to this product: the reviewed workflow does
not visibly change each source-native consumer, bind native validation receipts
to one reconciled campaign, and refuse on stale or missing receipts.

### Datafold

The closest execution and validation competitor. Its Data Migration Agent
documents broad SQL translation, self-correction, and dataset-, column-, and
row-level parity using a data knowledge graph.

Current documented boundary: its migration workflow is focused on data
platform and transformation migration. The reviewed public material does not
show heterogeneous downstream BI, pipeline, notebook, and model consumers
being mutated and closed inside a DataHub-native field-retirement campaign.

This boundary can move quickly and must be reviewed honestly.

### dbt Wizard

A direct competitor for the dbt executor. It understands dbt lineage, compiled
state, tests, contracts, and metrics; it can refactor and validate coordinated
project changes.

Retirement Conductor should delegate or coexist. “An agent updates a dbt
model” is not differentiated.

## Capability matrix

The matrix describes reviewed public behavior and intentionally avoids claims
about private features.

| Product | Cross-system inventory | Native consumer mutation | Native validation | Unified evidence closure | Producer-side refusal |
|---|---|---|---|---|---|
| DataHub | strong graph and context | metadata mutation, not general consumer source | assertions and connected context, not general migration proof | not visibly shipped as this loop | custom integration possible |
| Atlan | strong graph, owners, priority | not visibly automated in reviewed lifecycle workflow | not visibly source-native across platforms | workflow and audit are close | deprecation follows communication in example |
| Datafold | strong migration knowledge graph and BI context | strong for SQL and platform migrations | strong parity evidence | strong within its migration scope | not documented as a DataHub-bounded field-retirement gate |
| dbt Wizard | dbt scope | strong in dbt | strong in dbt | dbt-scoped | no cross-system authority |
| Retirement Conductor target | DataHub plus declared evidence sources | exact Git/dbt branch mutation | dbt-native parse, build, and semantic tests | one reconciled state; non-repository consumers stay blocking | deterministic gate |

## Strategic wedge

The wedge is not superior code generation. It is:

- DataHub-centered cross-platform inventory;
- one concrete Git/dbt receipt protocol plus strict external-receipt validation;
- native validators rather than generic confidence;
- freshness and source-version enforcement;
- continuous invalidation when graph or source state changes;
- one explainable gate in the producer workflow.

## Fast-follower threats

- DataHub could add an action workflow specialized for deprecation.
- Atlan could connect its lifecycle control plane to native migration agents.
- Datafold could expand from data-platform migrations into downstream consumer
  mutation.
- dbt or BI vendors could expose cross-platform campaign receipts through
  catalog partnerships.
- an internal platform team could assemble the loop from DataHub Actions,
  native agents, CI, and a workflow engine.

The answer is not broader feature count. The product must make the protocol
easy to adopt, auditable, portable across DataHub editions, and demonstrably
safer than a custom workflow.

## Positioning guardrails

Say:

- catalogs find likely blast radius; Retirement Conductor owns verified
  completion;
- native agents and validators remain authoritative in their domains;
- readiness is bounded by declared evidence;
- the market is fragmented and close competitors exist.

Do not say:

- no direct competitor exists;
- DataHub cannot support lifecycle workflows;
- source-native products cannot validate migrations;
- every consumer can be discovered;
- one receipt proves global safety.
