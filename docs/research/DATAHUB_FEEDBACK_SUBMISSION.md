# DataHub feedback submission

## 1. Which parts of DataHub felt polished or useful during your build?

The most useful part was cross-platform lineage as an operational input, not
just a visualization. Our repository scan found one consumer of
`orders.legacy_status`; the same bounded inventory in DataHub Core 1.6.0 found
31 downstream consumers—21 datasets, 6 charts, and 4 dashboards—over seven
pages. Even after conservatively assuming the repository match overlapped one
graph entity, DataHub added at least 30 known consumers.

The important result was consequential: after we migrated and natively
validated the one dbt consumer, adding a late Spark consumer changed the same
campaign from `READY_TO_RETIRE` to `UNSAFE` and our producer gate refused the
breaking change. That was the moment DataHub stopped being catalog decoration
and became the reason we avoided a bad operation.

The official
[Superset connector](https://docs.datahub.com/docs/generated/ingestion/sources/superset)
was another “just worked” path in an isolated worktree. DataHub 1.6.0 ingested
our selected virtual dataset, chart, dashboard, owner, and lineage without
warnings. The docs clearly label its authority as table-level lineage, which
matched what we observed and helped us know when to reread native Superset SQL
for exact field evidence. We also updated one stable DataHub document four
times and read back the exact content without changing the dataset's
deprecation state; that was a clean shared-memory primitive for another agent.

## 2. Where did you get stuck or lose time?

We lost the most time proving that lineage was complete and current. The MCP
surface was pleasant for agent search and context, but our safety-sensitive
path needed three different surfaces: MCP for discovery, GMS GraphQL for
counted paging and `skipCache`, and direct `upstreamLineage` aspect reads for
exact field evidence.

The reason was observable, not theoretical. We warmed a degree-two downstream
query at zero, wrote a late consumer, and waited until a cache-bypassed direct
query saw the new edge. The default root query still returned `total=0`; the
same query with `SearchFlags.skipCache=true` immediately returned `total=1`.
Core returned `isPartial: null` and `freshness: null` in both responses, while
MCP `get_lineage` exposed no cache-bypass argument. In another rerun the new
edge was still not visible inside our original 10-second observation bound, so
we had to retain bounded polling and source timestamps rather than trust a
successful write response.

We hit the same parity problem at field level: direct aspects contained an
exact two-hop field chain, but MCP column lineage returned only hop one. Our
workaround was conservative—MCP can add evidence, but it cannot exclude a
consumer found by cache-bypassed GMS paging. That is safe, but it is a lot of
integration code for every team that wants to automate a destructive schema
change.

## 3. If you had unlimited engineering time on DataHub, what would you build or fix first?

I would make **evidence-grade lineage enumeration** one identical contract
across MCP, GraphQL, and the SDK. Every response would include a stable snapshot
cursor, `returned`, `total`, `hasMore` or `nextCursor`, an explicit partial or
truncation reason, effective permission scope, cache-used/cache-bypassed state,
an index watermark, a connector/source watermark, and edge granularity such as
`FIELD_EXACT`, `TABLE_ONLY`, or `UNKNOWN`. MCP would expose a documented fresh
read mode instead of forcing agents to fall through to GraphQL.

I would ship that contract with a conformance suite built around the cases that
hurt us: more results than one page, a new edge after page one is cached, a
two-hop renamed-column chain, connector-level table lineage, a permission-
filtered branch, and an intentionally partial page. The same truth graph should
produce equivalent membership and completeness metadata through all three
clients.

Why it matters: ordinary impact analysis can tolerate “best effort.” An agent
that opens migration PRs or a CI gate that permits a column deletion cannot.
It must distinguish “there are no consumers” from “none were returned because
pagination, caching, permissions, indexing, or lineage granularity hid them.”
Making that distinction a DataHub primitive would let teams build trustworthy
automation on the graph instead of rebuilding a second evidence layer beside
it.

## 4. Any bugs, errors, or unexpected behavior?

### MCP offset pagination can silently hide consumers

On MCP server 0.6.0, `get_lineage` documents pagination and accepts `offset`.
Against a synthetic graph where DataHub reported 41 downstream entities, we
called `get_lineage(upstream=false, max_hops=3, max_results=1, offset=0)`.

- Expected: one result, `hasMore=true`, then a different result at `offset=1`.
- Actual: offset 0 returned one result with `total=41` but `hasMore=false`;
  offset 1 returned zero results and `hasMore=false`.
- Control: direct GMS `searchAcrossLineage(start=1,count=1)` returned one
  result, so the second server-side row existed.
- Error: none. The incorrect page looked complete, which is more dangerous
  than a visible failure.

We traced this to the MCP implementation requesting `start:0`, then applying
the offset locally after fetching only `max_results` rows. We opened
[issue 194](https://github.com/acryldata/mcp-server-datahub/issues/194) and a
[regression-tested fix in PR 195](https://github.com/acryldata/mcp-server-datahub/pull/195).
As of 2026-08-09, both were still open and the PR was review-required.

### Default lineage reads can remain stale after a successful edge write

We first cached a zero-result degree-two query, wrote a late edge, and verified
the edge was visible from its intermediate node. The default root query still
returned zero; the identical query with `skipCache=true` returned the late
consumer. We expected either the new edge or metadata saying the response was
cached/stale. Instead, `freshness` and `isPartial` were null. MCP had no
equivalent bypass input.

### MCP multi-hop column lineage stopped at hop one

We wrote and directly reread two exact field edges:
`legacy_status → model.order_status → late.order_status`. Calling
`get_lineage(column="legacy_status", upstream=false, max_hops=3)` returned
only the degree-one model with `total=1` and `hasMore=false`; the degree-two
consumer was absent. We expected the documented multi-hop column path, or an
explicit limitation saying only the first field hop was supported. No error or
limitation was returned.

All new reproductions used disposable loopback DataHub Core 1.6.0 and MCP
0.6.0 over synthetic metadata; no production system or lifecycle state was
mutated. The tracked evidence digest is
`sha256:22e883aed2c35f78e9d49df177f64bcd649d9732407ef33405a287a210ac6905`.
