# Winning workstreams coordination plan

**Planning snapshot:** `fc0121b` on 2026-08-09 UTC

**Planning branch:** `codex/winning-workstreams-plan`

**Purpose:** coordinate parallel, production-shaped work without weakening the
failure-closed product or creating avoidable merge conflicts.

## Decision

The next work is not another presentation pass and it is not broader feature
count for its own sake. The four highest-upside workstreams are:

1. a complete model-driven campaign over real disposable DataHub and Git/dbt
   state, including both successful work and later refusal;
2. model-authored semantic validation planning followed by an actual GitHub
   pull request and commit-bound CI evidence;
3. continuous fresh reconciliation that invalidates an issued Retirement
   Lease when DataHub observes new or stale evidence;
4. a strictly kill-gated Apache Superset executor that is implemented only if
   a disposable native system can supply exact identity, bounded mutation,
   native query proof, compensation, and fresh DataHub reconciliation.

These workstreams directly improve the judging dimensions instead of merely
adding surface area:

| Workstream | DataHub use | Technical execution | Originality | Usefulness | Submission legibility |
|---|---|---|---|---|---|
| Real agent campaign | proves runtime context, write-back, and model tool use | proves the complete existing engine | shows the authority split in operation | demonstrates an operator job end to end | supplies the central video story |
| Semantic plan and PR | grounds model judgment in DataHub context | binds proposal, approval, Git, PR, CI, and dbt evidence | makes the model useful without making it authoritative | places work in the normal team workflow | leaves a reviewable public artifact |
| Continuous lease revocation | repeatedly rereads DataHub rather than trusting a prior result | proves state and evidence drift handling | turns revocable readiness into a live control | protects the gap between approval and producer action | creates the strongest failure moment |
| Superset native executor | joins DataHub BI identity to its source system | proves a second native authority under the same receipt protocol | demonstrates that the protocol is not a dbt wrapper | closes one real non-repository consumer | makes heterogeneous orchestration visible |

## Non-negotiable truth rules

- No workstream may manufacture a decision by editing the campaign store,
  fixture manifest, or public artifact.
- A late consumer must be written to or ingested into disposable DataHub and
  then discovered by the normal inventory or reconciliation boundary.
- A model proposal is never authorization, native validation, closure, or
  readiness.
- An HTTP 2xx response, Git commit, pull request, CI label, screenshot, owner
  acknowledgment, or disappearing lineage edge is not by itself a native
  validation receipt.
- Every apply remains digest-bound, allowlisted, opt-in, and preceded by a
  fresh source precondition.
- Every new live claim records source versions, evidence mode, scope,
  pagination, freshness, limitations, artifact digests, and inspection.
- Fixture and fake-server tests are useful implementation evidence but cannot
  satisfy a live acceptance row.
- `READY_TO_RETIRE` remains bounded by the recorded evidence envelope.

## Workstream ownership

### WS-01 — real agent campaign and judge proof

- **Status:** already assigned on
  `codex/agent-demo-and-datahub-contributions`.
- **Brief:** `01-real-agent-campaign.md`.
- **Primary ownership:** agent acceptance runner, agent trace artifacts,
  interactive demo runbook, demo script, sample migration evidence.
- **Other agents must not edit:**
  `scripts/run_agent_acceptance.py`,
  `artifacts/public/agent/`, or
  `docs/runbooks/AGENT_DEMO.md` until WS-01 freezes.

### WS-02 — semantic migration plan and GitHub PR

- **Suggested branch:** `codex/semantic-pr-agent`.
- **Brief:** `02-semantic-pr-workflow.md`.
- **Primary ownership:** new semantic-plan schema and implementation, safe dbt
  test materialization, GitHub PR boundary, PR/CI receipts, focused tests.
- **Shared hotspots:** `agent_mcp.py`, `git_dbt.py`, `git_dbt_workflow.py`,
  `cli.py`, `pyproject.toml`, and `uv.lock`.

### WS-03 — continuous reconciliation and Retirement Lease revocation

- **Suggested branch:** `codex/continuous-retirement-lease`.
- **Brief:** `03-continuous-reconciliation.md`.
- **Primary ownership:** a new watcher module, watch receipts/events, lease
  status projection, live late-consumer acceptance, focused tests.
- **Shared hotspots:** `cli.py`, `store.py`, `events.py`, `gate.py`, schemas,
  and the agent MCP tool registry.

### WS-04 — bounded Superset native executor

- **Suggested branch:** `codex/superset-native-executor`.
- **Brief:** `04-superset-native-executor.md`.
- **Status:** starts with a hard feasibility gate; implementation is forbidden
  until that gate passes with a disposable real Superset and DataHub Core.
- **Primary ownership:** new Superset modules, disposable deployment, exact
  identity evidence, native validation, compensation, and focused tests.
- **Shared hotspots:** CLI registration, campaign workflow registration,
  configuration references, schemas, and package metadata.

## Branch and worktree protocol

1. Never put two active agents in one worktree.
2. Start every implementation worktree from the same frozen integration base.
   The preferred base is the merge commit that lands WS-01 on `main`.
3. If work begins before WS-01 merges, record the base commit and rebase once,
   immediately before integration. Do not repeatedly merge the active agent
   branch into a feature branch.
4. Runtime branches add only their feature-specific implementation, tests,
   schemas, runbook, and evidence generator. They do not independently rewrite
   `GOAL.md`, `STATUS.md`, `README.md`, `PLAN.md`, `docs/PRODUCT.md`, the
   architecture, contracts, risks, decisions, or evidence ledger.
5. Each branch writes required controlling-document changes into its own
   `docs/plans/integration-notes-<workstream>.md`. The integration owner makes
   the final coherent shared-document update after live acceptance passes.
6. Never resolve a shared-file conflict by accepting an entire side. Reapply
   the minimal registrations to the post-merge file and rerun focused tests.
7. A workstream that fails its stop condition is not partially merged for
   narrative value.

## Shared-file conflict map

| File or area | Owner before integration | Rule |
|---|---|---|
| Agent trace runner and agent public evidence | WS-01 | frozen before other agent-evidence work merges |
| Semantic-plan schema and implementation | WS-02 | new files; no other workstream edits them |
| GitHub PR/CI boundary | WS-02 | new files; no other workstream shells out to `gh` |
| Watcher and lease-status implementation | WS-03 | new files; no other workstream creates a scheduler |
| Superset modules and deployment | WS-04 | new files; no generic adapter framework |
| `agent_mcp.py` | integration owner | workstreams submit minimal registration hunks |
| `cli.py` | integration owner | workstreams submit minimal subcommand hunks |
| `store.py`, `events.py`, `gate.py` | WS-03 first, integration owner afterward | WS-02 and WS-04 use existing store APIs where possible |
| Product and controlling docs | integration owner | updated only after accepted behavior exists |
| Public site and final video | submission owner | consume accepted artifacts; never recompute policy |

## Recommended merge order

1. Merge WS-01 and freeze the agent tool contract used by the central demo.
2. Merge WS-02 because it extends the existing Git/dbt vertical and creates
   the real review artifact.
3. Rebase and merge WS-03; exercise revocation against the WS-02 PR-bound
   campaign.
4. Merge WS-04 only if every feasibility and live acceptance condition passes.
5. Perform one integration-only documentation and public-artifact commit.
6. Run the strongest repository, package, installed-wheel, live-local, agent,
   and browser validations before changing the default branch or submission.

## Integration acceptance

The combined candidate is acceptable only when all merged capabilities prove:

```text
natural-language intent
  -> direct DataHub context
  -> bounded complete campaign inventory
  -> model-proposed, kernel-validated semantic plan
  -> external human approval
  -> exact native change
  -> reviewable GitHub PR
  -> dbt-native proof bound to the PR head
  -> fresh DataHub reconciliation and write-back
  -> short-lived Retirement Lease
  -> actual new DataHub evidence
  -> automatic lease invalidation and producer refusal
```

If WS-04 passes, the same campaign must also close one Superset consumer
through a Superset-native receipt. Otherwise the public claim remains Git/dbt
only and Superset remains absent from supported scope.

## Explicitly deferred

These are not selected for parallel implementation now:

- an embedded model-provider abstraction—the connected coding-agent runtime is
  already a valid model host;
- a generic adapter framework—only a proved second executor can justify an
  interface extraction;
- DataHub Agent Registry support—it currently introduces a Cloud enablement
  boundary that cannot substitute for Core evidence;
- a custom visual control plane—the current operator and agent surfaces should
  consume the same canonical state first;
- multi-agent role playing—parallel engineering is useful, but the product
  does not need fictional agents in place of authority boundaries;
- acceptance of generic external receipts without a native verifier—this
  would weaken the central safety claim.
