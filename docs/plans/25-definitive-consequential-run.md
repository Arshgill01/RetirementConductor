# CP-05 — definitive consequential integration and comparison

## Launch condition

Do not start this task until CP-01 through CP-04 each have a clean tested
commit, public evidence, integration notes, and an explicit recommendation.

Start from a fresh worktree based on `codex/next-proof-workstreams-plan`.
Inspect every foundation report before merging or cherry-picking its commit.
Do not integrate a workstream merely because its final message says it passed.

## Objective

Produce one authoritative live-local result that answers all of these:

1. Can a heterogeneous Git/dbt plus Superset campaign pass full gate-time
   native refresh?
2. Can the same one-use producer authority control an actual PostgreSQL column
   retirement rather than a sentinel?
3. Does an unsafe retirement cause a real downstream workload failure?
4. Does Retirement Conductor produce a materially better result than static
   sign-off and a fair fresh-check CI alternative?

## Integration decisions before execution

From the inspected foundation evidence, record `KEEP`, `SIMPLIFY`, `REMOVE`,
`REFRAME`, or `INCONCLUSIVE` for each component. Then make the smallest shared
contract changes necessary.

Expected integration surfaces include:

- producer plan and receipt contracts capable of representing either the
  existing public-safe sentinel or the exact PostgreSQL action;
- one concrete PostgreSQL producer action in `ProducerGateWorkflow` without a
  generic arbitrary-SQL plugin system;
- final gate invocation of the Superset native verifier for every accepted
  Superset receipt;
- canonical source-observation comparison across DataHub, Git/dbt, Superset,
  and the producer schema;
- explicit action-intent and outcome semantics for a destructive native
  operation;
- CLI support only for the separately privileged producer workflow;
- no MCP tool that gives the general agent a warehouse mutation credential;
- backward compatibility or an explicit migration for existing sentinel
  evidence and stores.

Update contracts, decisions, risks, requirements, status, product boundary,
and evidence ledger only after the corresponding live evidence is inspected.

## Security boundary

The Codex/agent process may inventory, plan, migrate consumers, validate,
reconcile, publish, and prepare a producer plan. It must not possess the
PostgreSQL mutation credential.

The separately privileged producer process must:

- receive the exact issued plan and trusted run context;
- call the final gate and action in one trusted invocation;
- have permission only for the frozen disposable producer tuple;
- record intent before mutation;
- avoid blind retry after an ambiguous response;
- publish no credentials or rows.

The real action remains confined to a disposable local database. Do not imply
production deployment or eliminate the unavoidable race outside the native
transaction boundary.

## Required live topology

- disposable DataHub Core at a pinned version;
- disposable Git/dbt repository and native validation environment;
- disposable Superset with official connector ingestion and direct aspect
  reread;
- disposable PostgreSQL producer with separate observer, consumer, and
  mutation principals;
- CP-04 downstream workload, preferably pinned Spark/JDBC when its evidence
  passed;
- one persistent Retirement Conductor campaign store per product run;
- isolated fresh environments for each comparison arm.

Do not reuse a mutated database between arms. Every arm starts from a verified
byte-equivalent or digest-equivalent seed.

## Definitive sequences

### A. Heterogeneous clean control with real action

```text
resolve exact field pair in DataHub
  → inventory Git/dbt and Superset consumers
  → separately plan and authorize exact native changes
  → apply Git/dbt and Superset changes
  → pass dbt and forced Superset native validation
  → reingest and directly reread DataHub
  → reconcile to READY_TO_RETIRE
  → publish and verify summary
  → issue short-lived Retirement Lease
  → final gate rereads DataHub, Git/dbt, Superset, and producer schema
  → separately privileged process drops legacy_status
  → native schema reread proves absence
  → replacement workload succeeds
  → replay of the same lease refuses
```

This sequence must prove one and only one committed destructive action.

### B. Late-consumer prevention

```text
prepare an equivalent ready campaign and issued lease
  → execute and ingest the real late downstream workload descriptor
  → fresh observation changes canonical state
  → prior lease becomes INVALIDATED
  → preserved producer plan refuses
  → destructive statement count remains zero
  → producer schema reread proves legacy_status present
  → legacy downstream workload remains healthy
```

### C. Unsafe static consequence

Run the frozen static arm on its own disposable environment:

```text
initial point-in-time report, validation, and approval are green
  → introduce the identical late consumer
  → do not refresh by contract
  → exact producer drop commits
  → legacy workload fails with attributable missing-column outcome
```

This is not a named-vendor claim. It is the defined consequence of reusable
point-in-time authority.

### D. Fair fresh-check CI comparison

Run the identical intervention through the competent fresh-check baseline.
It should normally detect the late consumer and refuse. Then run the frozen
replay, approval drift, Superset drift, source drift, unavailable evidence,
and lost-response scenarios required by CP-03.

If fresh CI matches Retirement Conductor's safety, say so. The final product
advantage may be limited to one-use authority, durable recovery, and causal
audit—or may be absent.

### E. Failure and recovery

At minimum exercise:

- Superset native drift after reconciliation;
- producer schema drift after lease issue;
- DataHub outage at gate time;
- PostgreSQL permission loss;
- crash before destructive execution;
- lost response after action intent;
- plan replay after success;
- store/artifact tampering;
- stale or expired lease;
- clean rerun after deterministic environment reconstruction.

## Comparative decision

Use the frozen CP-03 decision rule unchanged:

- `MATERIALLY_BETTER`;
- `SAFETY_EQUIVALENT_PROTOCOL_ADVANTAGE`;
- `NO_MATERIAL_ADVANTAGE`;
- `WORSE`;
- `INCONCLUSIVE`.

Do not add or remove metrics after observing results. Publish per-arm facts,
not only the classification.

## Acceptance invariants

- The clean product control drops exactly one column and never falsely blocks.
- The replacement field and replacement workload remain valid after the drop.
- Every unsafe or unavailable product case leaves the column present unless an
  already-recorded outcome-unknown action is later natively resolved as
  committed.
- A late consumer makes prior authority operationally unusable.
- Gate-time Superset drift refuses before PostgreSQL mutation.
- The general agent has no producer mutation credential or action tool.
- Static unsafe execution produces the attributable downstream failure.
- Fresh CI is evaluated fairly and failure-closed.
- Every arm uses equivalent initial state and the same destructive action.
- Public evidence is digest-bound, path-safe, secret-safe, and independently
  verifiable offline.

## Evidence package

Publish under:

```text
artifacts/public/definitive-consequential-run/
```

Include:

- top-level self-verifying index;
- exact commits, source versions, image identities, and frozen input digests;
- per-arm action, schema, workload, and refusal outcomes;
- Superset gate-time verification evidence;
- real PostgreSQL action plan and safe receipt;
- before/after native schema digests;
- downstream workload health/failure digests;
- replay and outcome-unknown recovery evidence;
- comparative matrix and unmodified decision rule;
- observed failures and repairs during the run;
- limitations and explicit non-production scope.

Raw credentials, rows, unrestricted SQL results, raw model reasoning, host
paths, and cookies remain ignored.

## Validation

Before completion:

1. run each foundation verifier against its promoted evidence;
2. run targeted contract, gate, PostgreSQL, Superset, and comparison tests;
3. run the clean and negative live sequences from fresh environments;
4. inspect native schema and workload outcomes, not only exit codes;
5. run clean package installation and installed-wheel producer workflow;
6. run `make check`;
7. run secret and public-artifact scans over the final evidence;
8. verify `git diff --check` and a clean worktree.

## Completion and reframe rules

- Promote PostgreSQL as a supported disposable/reference producer action only
  if the exact native success, refusal, replay, and outcome-unknown behavior
  pass.
- Promote Superset beyond experimental only if the final gate performs its
  independent native refresh and all drift/outage cases refuse.
- Retain the Retirement Lease claim only at the strength supported by the fair
  comparison classification.
- If the baseline matches every meaningful property with less machinery,
  simplify or reframe the product rather than burying the result.
- Keep RC-018 independent operation as a separate honest `NOT_RUN` boundary;
  this integration run is still author-operated engineering evidence.
