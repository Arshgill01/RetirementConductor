# DataHub feedback submission

These four answers are sized for the four separate Devpost textarea fields.
The linked worklog and public-safe artifacts retain the longer evidence trail.

## 1. Which parts of DataHub felt polished or useful during your build?

The most useful part was cross-platform lineage as an operational input, not
just a visualization. Our repository scan found one consumer of
`orders.legacy_status`; the same bounded inventory in DataHub Core 1.6.0 found
31 downstream consumers over seven pages: 21 datasets, 6 charts, and 4
dashboards. Even if the repository match overlapped one graph entity, DataHub
added at least 30 known consumers.

That context changed a real decision. After we migrated and natively validated
the one dbt consumer, the campaign was `READY_TO_RETIRE`. Adding a late Spark
consumer and reconciling against DataHub changed it to `UNSAFE`, and our
producer-side gate refused the breaking change. DataHub was the reason the
automation stopped rather than deleting a still-used field.

Two smaller paths also felt polished. The official
[Superset connector](https://docs.datahub.com/docs/generated/ingestion/sources/superset)
ingested our selected virtual dataset, chart, dashboard, owner, and table
lineage on DataHub 1.6.0 with no warnings. Its docs explicitly say the lineage
authority is table-level, which helped us know when native Superset SQL was
still required for exact field evidence. Also, MCP `save_document` let us
update one stable campaign document four times and read back the exact content
without touching the dataset's deprecation state. That worked well as durable
shared memory between agents.

## 2. Where did you get stuck or lose time?

We lost the most time establishing whether a lineage result was complete
enough to authorize a destructive change. The agent-friendly MCP surface was
excellent for discovery, but our safety path ended up using MCP for context,
GMS GraphQL for counted paging and a cache-bypassed read, and direct
`upstreamLineage` aspects for exact field evidence.

The biggest time sink was that MCP's documented pagination looked successful
while silently stopping after page one. On a clean 31-neighbor graph,
`get_lineage(max_results=1, offset=0)` returned one row with `total=31` but
`hasMore=false`; `offset=1` returned zero. We had to trace the request through
the MCP implementation and compare it with direct GMS
`searchAcrossLineage(start=1,count=1)`, which did return the second row. There
was no error to lead us there.

The docs explain individual APIs and connector capabilities, but I could not
find one end-to-end guide for “enumerate every downstream consumer safely.” A
useful guide would cover paging, cache/index freshness, permission-filtered or
partial results, field-versus-table granularity, and which read surface is
authoritative for each claim. Without that, every team building migration or
governance automation has to rediscover the same boundaries.

## 3. If you had unlimited engineering time on DataHub, what would you build or fix first?

I would build an **evidence-grade lineage read contract** shared by MCP,
GraphQL, and the SDK. A lineage enumeration would use a stable snapshot cursor
and always return `returned`, `total`, `nextCursor`/`hasMore`, an explicit
partial or truncation reason, effective permission scope, cache-used or
cache-bypassed state, index and connector/source watermarks, and edge
granularity such as `FIELD_EXACT`, `TABLE_ONLY`, or `UNKNOWN`. MCP would expose
a documented fresh-read mode instead of requiring agents to fall through to
GraphQL.

I would ship it with a conformance suite using the cases that matter in
practice: more results than one page, a new edge after page one was cached, a
two-hop renamed-column chain, connector-provided table-only lineage, a
permission-filtered branch, and an intentionally partial response. The same
truth graph should produce equivalent membership and completeness metadata
through every supported client.

This matters because ordinary exploration can tolerate “best effort,” but an
agent that opens migration PRs or a CI gate that permits a column deletion
cannot. It must distinguish “no consumers exist inside this declared evidence
scope” from “none were returned because paging, caching, permissions, indexing,
or granularity hid them.” Making that distinction a DataHub primitive would
let teams automate high-consequence changes without rebuilding a second
evidence system beside the graph.

## 4. Any bugs, errors, or unexpected behavior?

**Bug: MCP `get_lineage` offset pagination can silently hide consumers.**

Environment: brand-new project-scoped Docker volumes, DataHub Core 1.6.0, and
MCP server 0.6.0 at commit `9a6946d`; all metadata was synthetic and loopback.

1. Seed a graph with 31 downstream entities.
2. Call `get_lineage(upstream=false,max_hops=3,max_results=1,offset=0)`.
3. Call the same tool with `offset=1`.

Expected: page one returns one row with `hasMore=true`; page two returns a
different row.

Actual: page one returned one row with `total=31` and `hasMore=false`; page two
returned zero rows and `hasMore=false`. There was no error. As a control,
direct GMS `searchAcrossLineage(start=1,count=1)` returned one row, proving the
second server-side result existed.

The implementation sent `start:0` to GraphQL and then applied `offset` locally
after fetching only `max_results` rows. This is tracked in
[issue 194](https://github.com/acryldata/mcp-server-datahub/issues/194) and
[PR 195](https://github.com/acryldata/mcp-server-datahub/pull/195). We checked
out the PR head (`4f2a712`) and repeated the identical experiment: page one
changed to `hasMore=true`, page two returned one row, and the defect predicate
changed from true to false. The PR's focused regression test also passed
(`1 passed`). As of 2026-08-09 the issue and PR were still open, so this is a
verified proposed fix, not a released fix.

The released and patched run digests are respectively
`sha256:3c9dbe4e507f3a2d146daa46f26618189b77905261688e2c5bbcd021dc90acf5`
and
`sha256:86729d9e86867728a92358a1a74bcef0fa463364564c28568e355fbde9b4f240`.
Two earlier retained-state suspicions—stale default reads and truncated
multi-hop column lineage—did not reproduce on the clean stack and are excluded
from this bug report.
