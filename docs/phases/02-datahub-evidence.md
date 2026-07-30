# Phase 02 — DataHub evidence boundary

## Outcome

The product resolves one live field identity, inventories its downstream
consumers through DataHub with an explicit coverage envelope, stores the raw
redacted observations, and publishes and reads back one stable campaign
summary without overstating completeness.

## Dependencies

- phase 01 campaign kernel and durable state;
- disposable DataHub Core environment;
- public-safe cross-platform sample graph;
- runtime credentials supplied only through ignored configuration.

## Scope

In scope:

- DataHub Core read path through self-hosted MCP;
- GraphQL or SDK fallback for complete pagination or required mutation;
- live capability and version inspection;
- search-based target and replacement resolution;
- schema, owner, lineage, path, and permitted query context;
- coverage-envelope construction;
- stable document or supported metadata write/read-back;
- Core versus Cloud capability reporting.

Excluded:

- native consumer mutation;
- DataHub as the campaign transaction store;
- lifecycle deprecation while blockers exist;
- claims that query or lineage absence proves safety;
- requiring Cloud-only features for the complete path.

## Deliverables

- DataHub configuration contract with secret references;
- capability fingerprint;
- canonical entity resolver;
- complete downstream pager;
- evidence normalizer retaining raw artifact links;
- coverage-envelope builder;
- baseline and reconciliation snapshot format;
- stable summary publisher and read-back verifier;
- disposable environment runbook;
- live, pagination, freshness, permission, and writeback tests.

## Work breakdown

1. Start the pinned disposable Core environment safely.
2. Record server, CLI, MCP, SDK, and connector versions.
3. Inspect the live MCP tool list and GraphQL schema.
4. Resolve target and replacement from native components; reject zero or
   multiple canonical matches.
5. Retrieve schema fields and confirm both field identities.
6. Traverse downstream lineage at configured depth.
7. Page to advertised termination and compare counts.
8. Retrieve exact paths for selected consequential consumers.
9. Capture ownership only as routing evidence.
10. Retrieve query context and record actual exposed retention or its absence.
11. Build the evidence envelope with freshness and limitation status.
12. Publish a blocked campaign summary at one stable identity.
13. Update it idempotently and read it back through an agent-visible surface.
14. Verify the target lifecycle remains unchanged.

## Acceptance evidence

Required behavior:

- target and replacement are resolved from the running instance;
- an ambiguous or missing identity refuses;
- inventory records hop depth, filters, total, returned count, pages,
  truncation indicators, times, versions, and errors;
- a forced page failure makes the required source partial and blocks;
- stale ingestion or evidence exceeds policy and blocks;
- query-history absence records no observations and never closes a consumer;
- ownership never becomes validation;
- removing DataHub materially reduces the actionable inventory in the
  representative graph;
- stable summary update produces one logical record;
- read-back exposes decision, blockers, evidence-envelope digest, and manifest
  digest;
- lifecycle mutation remains absent.

Required commands:

```bash
make check
retirement-conductor datahub preflight
retirement-conductor campaign inventory --campaign <id>
retirement-conductor campaign publish --campaign <id>
retirement-conductor campaign verify-publication --campaign <id>
git diff --check
```

Inspect:

- capability fingerprint;
- raw paginated responses;
- normalized consumer identities;
- evidence envelope;
- DataHub summary and read-back;
- target lifecycle before and after.

## Stop or reframe conditions

- If DataHub does not add consequential scope beyond configured repository
  evidence, reframe toward a repository-native migration product.
- If complete pagination cannot be achieved through any supported live
  surface, keep the source incomplete and do not proceed to readiness.
- If stable summary write/read-back is unavailable, preserve local campaign
  correctness and document a different agent-visible DataHub surface before
  continuing.

## Risks changed

- R-01 incomplete coverage;
- R-02 identity mapping;
- R-10 DataHub indispensability;
- R-11 Core and Cloud divergence;
- R-12 state authority;
- R-15 sensitive query evidence;
- R-17 graph disappearance.
