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

## Pass 3 — provisional focused probes

The first focused API/MCP probe reused the existing reference-service volumes.
It reproduced the MCP offset failure, but also suggested a stale default read
and a missing second field-lineage hop. Because those two observations could
have been influenced by retained synthetic state, they remained provisional.
The combined-degree omission from an older run did not reproduce at all and was
excluded immediately.

This pass was useful mainly as an adversarial checkpoint: it showed that a
live-local reproduction is not automatically a clean reproduction. No cache or
column-lineage claim from this pass survives into the submission without the
new-volume rerun below.

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

## Pass 5 — clean-stack reproduction and patch control

A new Docker Compose project named `retirement-conductor-feedback-clean` was
started with brand-new project-scoped MySQL, OpenSearch, and Kafka volumes. The
same experiment was then run against two MCP revisions while keeping DataHub
Core 1.6.0 and the synthetic 31-neighbor graph constant.

Released MCP 0.6.0 at `9a6946d`:

- page one: one result, `total=31`, `hasMore=false`;
- page two (`offset=1`): zero results;
- direct GMS control (`start=1,count=1`): one result;
- defect predicate: true;
- digest:
  `sha256:3c9dbe4e507f3a2d146daa46f26618189b77905261688e2c5bbcd021dc90acf5`.

PR 195 head at `4f2a712` on the identical Core stack and graph:

- page one: one result, `total=31`, `hasMore=true`;
- page two (`offset=1`): one result;
- direct GMS control (`start=1,count=1`): one result;
- defect predicate: false;
- digest:
  `sha256:86729d9e86867728a92358a1a74bcef0fa463364564c28568e355fbde9b4f240`.

The PR's own focused regression test passed (`1 passed`). This is a controlled
failing-before/passing-after result, but the submission still calls it a
proposed fix because the PR has not been released.

The clean run also rejected two provisional claims:

- the default lineage read saw the late edge, matching the cache-bypassed read;
- MCP column lineage returned both degree-one and degree-two results and matched
  the exact two-edge field chain in the direct aspects.

Those behaviors were consistent under both MCP revisions. They are recorded as
non-reproductions, not bugs.

Tracked artifacts:

- `artifacts/public/datahub-feedback/live-evidence.json` — released MCP;
- `artifacts/public/datahub-feedback/pr195-evidence.json` — PR 195 head.

## Pass 6 — live submission-form verification

The authenticated Devpost submission schema was read on 2026-08-09. It exposes
four separate `SubmissionFieldTextArea` fields matching the questions in the
prompt. The fields are optional at the schema level, but the prize opt-in says
that answering yes and filling them out makes the entrant eligible for one of
ten $50 awards. The connector returned no character limit, so the final file
keeps each answer compact while the worklog and JSON artifacts retain the full
audit trail.

## Final critique result

The form-ready draft now makes one main point per question, uses only the one
bug that survived clean isolation, and includes exact steps, expectations,
actual results, versions, a direct control, a patched control, limitations, and
upstream links. The clean verification loop materially changed the submission
by removing two plausible but unsupported bug claims.
