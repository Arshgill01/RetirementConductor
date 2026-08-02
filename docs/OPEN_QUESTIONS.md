# Open questions

These questions direct evidence gathering. They are not invitations to broaden
the implementation before the complete supported path works.

## Product

1. How often do DataHub customers retire or replace columns across more than
   one consumer platform?
2. Who owns the operation and who controls the producer change?
3. Is the dominant cost discovery, source migration, validation, coordination,
   or obtaining approval?
4. Do teams want a product, an embedded DataHub application, a CI action, or a
   repeatable internal runbook?
5. Which refusal outcome is most useful to an operator: missing access,
   missing owner, stale evidence, semantic uncertainty, or active consumer?
6. What evidence would a platform leader accept before permitting the producer
   change?
7. How often is a compatibility view or dual-read period preferable to direct
   consumer migration?

## DataHub

1. Which DataHub Core and Cloud versions must be supported first?
2. Which capability surface is most stable for complete lineage pagination:
   MCP, GraphQL, or SDK?
3. What freshness signal can be trusted for each connector?
4. Can ingestion run identity and sync status be bound cleanly to a graph
   snapshot?
5. Which metadata object should hold a campaign summary across Core and Cloud?
6. Can DataHub events drive a later consumer-change watcher without creating a
   second source of truth?
7. How should column-level identity survive schema evolution and connector
   naming changes?

## Native execution

1. What is the smallest dbt validation set that provides meaningful semantic
   evidence for a replacement?
2. How should macros, generated SQL, non-default branches, and `SELECT *` be
   represented in the coverage envelope?
3. Which external receipt format can close a non-repository consumer without
   weakening the Git/dbt-native evidence standard?
4. Which DataHub quality, assertion, incident, or contract aspects remain
   portable between Core and Cloud?
5. What compensation is possible for each native operation after partial
   failure?
6. Which source run identifiers are safe and sufficient for receipt
   provenance?

## Policy and trust

1. How fresh must inventory and validation receipts be at final gate time?
2. Which dispositions can a real organization permit, and who may authorize a
   waiver?
3. What evidence proves non-applicability rather than mere inactivity?
4. Should a ready campaign automatically reopen on every graph change, only on
   relevant target changes, or under a bounded observation window?
5. What principal signs or attests receipts if content authenticity becomes a
   requirement?
6. How should two campaigns coordinate when they touch the same consumer or
   replacement chain?
7. Which evidence must be deleted or redacted for privacy and retention
   policies?

## Adoption experiments

For each prospective operator, capture:

- a real recent retirement or rename;
- systems included and systems missed;
- manual steps and handoffs;
- validators actually trusted;
- whether the producer change was enforceably gated;
- failure or near-miss cost;
- tools already used;
- the smallest result they would adopt;
- the reason they would reject the product.
