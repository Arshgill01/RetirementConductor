# DataHub feedback worklog

This is a multi-pass evidence log for the four Build with DataHub feedback
questions. It is not the final submission. Claims are promoted only when a
tracked artifact, retained live-local run, inspected worktree, or linked
upstream issue supports them.

## Pass 1 — repository and worktree reconstruction

### Evidence inspected

- The completed product branch records a live DataHub Core 1.6.0 inventory of
  31 downstream consumers over seven GraphQL pages. The repository-only scan
  found one consumer, so the conservative minimum DataHub expansion was 30.
- A complete model-driven run moved one exact dbt consumer, passed dbt-native
  validation, published and read back a DataHub document, executed one bounded
  local sentinel, then reversed from `READY_TO_RETIRE` to `UNSAFE` when a late
  Spark consumer appeared.
- The unmerged continuous-reconciliation worktree independently reread one
  exact `legacy_status` to `order_status` field edge from the late consumer's
  `upstreamLineage` aspect. Its MCP observation preserved the consumer only as
  table-level evidence.
- The unmerged Superset worktree used the official DataHub 1.6.0 Superset
  connector successfully: selected dataset, chart, dashboard, ownership, and
  lineage were ingested without warnings or failures. Direct native SQL was
  still required for exact field authority because the connector contract is
  table-level.
- The unmerged semantic-PR worktree used live DataHub and dbt evidence to bind
  one reviewable PR. DataHub returned no glossary association or field-quality
  assertion for that graph, and empty query history was correctly retained as
  non-authoritative absence.

### Candidate polished points

1. Cross-system lineage materially changed an action, not just a screen: one
   repository match versus 31 DataHub consumers, followed by a late-consumer
   readiness reversal.
2. The official Superset connector completed a realistic ingestion without
   warnings and preserved stable native IDs needed for an exact reread.
3. `save_document` supported a stable create/update/read-back workflow without
   mutating dataset deprecation state.
4. MCP tool discovery is unusually descriptive: the live 0.6.0 server exposed
   typed schemas and detailed filter/pagination guidance for 20 tools.

### Candidate friction points

1. The agent-friendly MCP surface and the completeness-sensitive GraphQL/aspect
   surface are not equivalent. The build needed MCP for context, GraphQL for
   complete counted paging, and direct aspect reads for exact field evidence.
2. Core lineage responses omitted `isPartial` and cache freshness, while the
   MCP lineage tool exposed no cache-bypass argument.
3. Immediate document read-back was once delayed after a successful write, so
   verification had to poll the read without repeating the mutation.
4. The self-hosted Core path requires several services before GMS is healthy;
   this is operational friction, but it needs a timed clean-start result before
   becoming a submission claim.

### Claims explicitly excluded

- No production or DataHub Cloud behavior was tested.
- A fixture graph does not prove universal lineage completeness.
- Retained synthetic metadata that increased the current rich graph to 41
  consumers is not presented as a clean 41-consumer benchmark.
- Empty query history, ownership, a connector success counter, or a vanished
  edge is not treated as validation or closure.

## Pass 2 — fresh live-local campaign

On 2026-08-09, `make test-end-to-end` ran against disposable DataHub Core
1.6.0, MCP server 0.6.0, dbt Core 1.12.0, and DuckDB 1.5.5.

- Result: passed; the one-consumer path reached `READY_TO_RETIRE`, the late
  two-consumer path reached `UNSAFE`, and the retained rich graph reached
  `UNSAFE`.
- Focused policy, gate, and campaign-store tests: 39 passed.
- The late reconcile added exactly one consumer and produced
  `POLICY_CONSUMER_OPAQUE` plus `RECONCILIATION_NEW_CONSUMER`.
- The gate refused unavailable DataHub as `SOURCE_DATAHUB_UNAVAILABLE`, replay
  as `GATE_PLAN_REPLAYED`, source drift as `SOURCE_GIT_FILE_CHANGED` or
  `GATE_SOURCE_DRIFT`, and late membership as `GATE_DECISION_NOT_READY`.
- Ready publication and late publication both verified successfully in this
  run. This does not erase the earlier observed transient read-back delay.
- Raw public-safe command observations and durations are retained under the
  ignored run `run-e303bb5eb7bb`; the aggregate evidence digest is
  `sha256:6fde29c7227578e8eae99e3b24a4182be1484c4accdb9b7677c4fd965cc45a1b`.

## Pass 3 — focused API and MCP probes

`scripts/run_datahub_feedback_experiments.py` ran against DataHub Core 1.6.0
and MCP server 0.6.0, then restored the base graph. The tracked artifact is
`artifacts/public/datahub-feedback/live-evidence.json`, with evidence digest
`sha256:22e883aed2c35f78e9d49df177f64bcd649d9732407ef33405a287a210ac6905`.

- The live MCP server exposed 20 typed tools. `get_lineage` documented and
  accepted `offset`, but exposed no cache-bypass parameter.
- MCP offset defect reproduced: a retained synthetic graph reported `total=41`.
  With `max_results=1`, offset 0 returned one result and `hasMore=false`;
  offset 1 returned zero and `hasMore=false`. A direct GMS control with
  `start=1,count=1` returned one result. No error was raised.
- Cache behavior reproduced: after warming a degree-two zero, the late edge
  became visible through a cache-bypassed direct check. The default root query
  still returned zero, while the same cache-bypassed root query returned one.
  Both responses exposed `isPartial=null` and `freshness=null`.
- Multi-hop column discrepancy reproduced: direct `upstreamLineage` aspects
  contained the exact two-edge field chain, but
  `get_lineage(column="legacy_status", max_hops=3)` returned only the
  degree-one model, `total=1`, and `hasMore=false`.
- The older combined-degree omission did not reproduce. One combined
  cache-bypassed query returned both degree-one and degree-two consumers, equal
  to the union of individual degree queries. It is excluded from the current
  bug answer.
- An intermediate rerun did not observe the late edge inside the original
  10-second bound. The run failed without promoting evidence and restored the
  base graph. The successful final run observed it on attempt two after 9.4
  seconds under a widened 60-second bound.

## Pass 4 — primary-source and adversarial verification

The official MCP page says `get_lineage` supports pagination and hop control.
The official lineage API tutorial says `max_hops` traverses multi-hop lineage
and column results contain paths. The Superset source page explicitly promises
dashboards, charts, datasets, ownership context, and table-level lineage; this
matches the successful unmerged connector experiment and prevents us from
overclaiming field-level authority. The document tutorial confirms native
document creation, update, search, and SDK upsert behavior.

GitHub issue 194 and PR 195 were checked with authenticated `gh` on 2026-08-09.
Both were open; the PR was mergeable but review-required, with no reported
checks in the queried status. The submission therefore says “proposed fix,”
not “fixed upstream.”

The adversarial edit removed or demoted four weak claims:

- startup complexity, because no clean cold-start timing was retained;
- the older combined-degree omission, because it did not reproduce;
- the absolute 41-consumer count as product value, because retained volumes
  contain prior synthetic metadata;
- production, Cloud, or universal-completeness implications, because all new
  evidence is live-local Core over a synthetic graph.

## Final critique result

The form-ready draft now makes one main point per question, distinguishes
observed bugs from the requested evidence-grade contract, and provides exact
steps, expectations, actual results, versions, limitations, and upstream links.
