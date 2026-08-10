# Consequential product proof coordination plan

**Planning base:** `78c1970bbed690374a3cd883b51f9274307b576c`

**Planning branch:** `codex/next-proof-workstreams-plan`

**Purpose:** replace the remaining sentinel-only and partial multi-executor
boundaries with consequential native evidence, and fairly test whether
Retirement Conductor produces a materially better result than a credible
fresh-check CI alternative.

## Decision

Run four bounded foundation workstreams in parallel:

1. **PostgreSQL producer retirement action** — build one fixed, allowlisted,
   separately privileged `DROP COLUMN` action for a disposable producer.
2. **Superset gate-time refresh** — independently reread and revalidate the
   exact Superset native objects immediately before producer authority can be
   consumed.
3. **Realistic alternative ablation v2** — compare static sign-off, a fair
   failure-closed fresh-check CI workflow, and Retirement Conductor without
   assuming Retirement Conductor must win.
4. **Native breakage outcome lab** — execute an actual downstream workload and
   prove the observable consequence of an unsafe producer retirement.

After all four finish, run one sequential integration workstream. It is the
only task allowed to wire the new boundaries into the shared producer gate,
change canonical claims, or publish the final comparative conclusion.

No task in this plan performs demo, Workbench, website, video, Devpost,
submission-copy, or visual-design work.

## Why these four

The repository already proves two narrower claims:

- DataHub materially expands repository-only inventory and can reverse the
  decision.
- Under one inspected late-consumer intervention, an executable static
  sign-off remains green while a Retirement Lease invalidates and refuses.

Those results do not yet prove the strongest product thesis. The remaining
questions are:

- Can a real producer schema mutation be placed on the mandatory gate path?
- Can Superset satisfy the same final native-refresh contract as Git/dbt?
- Does Retirement Conductor beat a competent fresh-check CI implementation,
  or does that simpler alternative match it?
- Does preventing the action avoid a real downstream failure rather than only
  avoid writing a sentinel?

The workstreams isolate those questions so a successful result cannot be
attributed to choreography or a weak baseline.

## Hypotheses and nulls

| Question | Null hypothesis | Evidence that rejects the null |
|---|---|---|
| Does the gate control a consequential action? | The current sentinel proves only internal state-machine behavior. | A separately privileged disposable PostgreSQL workflow attempts the exact drop, a refusal leaves the column present, a clean run removes it, and replay cannot execute again. |
| Is Superset a complete campaign executor? | Its accepted receipt can drift after reconciliation without a gate-time native check. | The final gate independently rereads exact Superset identities, source fingerprint, saved chart, and semantic result; every drift or outage refuses. |
| Is Retirement Conductor better than fresh CI? | A small failure-closed DataHub pre-action check matches all relevant safety and recovery properties with less machinery. | Frozen identical scenarios show a predeclared advantage in unsafe actions, stale-authority reuse, replay, interruption recovery, or audit reconstruction without a clean-control regression. |
| Does prevention matter operationally? | Blocking a drop has no demonstrated consequence beyond a status transition. | The unsafe arm actually drops the column and breaks a real downstream workload, while blocked arms preserve both schema and workload health. |

An equal or losing result is valid evidence. If fresh-check CI matches the
campaign protocol on the predeclared measures, the integration task must
recommend `SIMPLIFY` or `REFRAME`, not alter the benchmark after observation.

## Dependency graph

```text
CP-01 PostgreSQL producer action ───────┐
CP-02 Superset gate-time refresh ───────┤
CP-03 realistic alternative ablation ──┼─→ CP-05 definitive consequential run
CP-04 native breakage outcome lab ──────┘
```

The four foundation tasks may run concurrently because they own separate new
modules, fixtures, deployments, and tests. CP-05 starts only after their final
reports and clean tested commits exist.

## Parallel task map

### CP-01 — PostgreSQL producer retirement action

- Brief: `docs/plans/21-postgres-producer-action.md`
- Suggested branch: `codex/postgres-producer-action`
- Owns: a concrete PostgreSQL action module and configuration, a disposable
  producer deployment, action-level tests, and task-local evidence.
- Does not edit the shared gate, CLI, MCP, schemas, or canonical documents.

### CP-02 — Superset gate-time refresh

- Brief: `docs/plans/22-superset-gate-time-refresh.md`
- Suggested branch: `codex/superset-gate-time-refresh`
- Owns: a read-only Superset gate verifier, source-observation normalization,
  focused tests, and live-local evidence.
- Does not edit `gate.py` or change supported-product claims.

### CP-03 — realistic alternative ablation v2

- Brief: `docs/plans/23-realistic-alternative-ablation-v2.md`
- Suggested branch: `codex/realistic-alternative-ablation-v2`
- Owns: the frozen protocol, independent oracle, baseline implementations,
  evaluator, reports, and tests.
- Must not modify product behavior to improve the Retirement Conductor arm.

### CP-04 — native breakage outcome lab

- Brief: `docs/plans/24-native-breakage-outcome-lab.md`
- Suggested branch: `codex/native-breakage-outcome-lab`
- Owns: isolated producer and downstream-workload deployment, deterministic
  data, workload probes, outcome oracle, evidence, and tests.
- Does not call or modify the Retirement Conductor gate.

### CP-05 — definitive consequential run

- Brief: `docs/plans/25-definitive-consequential-run.md`
- Suggested branch after CP-01 through CP-04: `codex/definitive-consequential-run`
- Integrates the four tested outputs, changes shared contracts deliberately,
  runs the live comparison, and records the final product decision.

## Service and workspace isolation

Each task uses its own worktree, ignored runtime root, Docker Compose project,
and ports. It must not reuse another task's campaign database or credentials.

| Task | Compose project | Reserved host surface |
|---|---|---|
| CP-01 | `rc_cp01_producer` | PostgreSQL `127.0.0.1:25432` |
| CP-02 | `rc_cp02_superset_gate` | DataHub `127.0.0.1:28080`, Superset `127.0.0.1:28088` |
| CP-03 | none by default | no live ports before integration |
| CP-04 | `rc_cp04_outcome_lab` | PostgreSQL `127.0.0.1:35432`; no public Spark port |

If a reserved port is occupied, the task may choose another loopback port but
must record it in private run evidence and keep public evidence path-safe.
Disposable services must be stopped at task completion unless the integration
notes explicitly ask the owner to retain them for inspection.

## Shared truth and safety rules

- Freeze every comparison scenario and expected outcome before running any
  product arm.
- Use the same initial graph, data, native action, validator, authorization,
  and late-consumer intervention across comparable arms.
- The fresh-check CI baseline must be competent and failure-closed. Do not
  omit pagination, freshness, source identity, or error handling merely to
  make Retirement Conductor look better.
- A real producer action is permitted only in the task's disposable database.
  Production endpoints, credentials, data, or infrastructure are forbidden.
- The only allowed destructive SQL is the exact schema/table/column tuple
  frozen in the task fixture. Arbitrary SQL and `CASCADE` are forbidden.
- The process that holds the producer mutation credential must be distinct
  from the general agent/MCP process.
- The model may plan and explain. Deterministic code owns authorization,
  source preconditions, gate verification, action execution, outcome
  classification, and final policy.
- A timeout after action intent is outcome unknown until a native schema
  reread resolves it. Never retry the destructive statement blindly.
- Public artifacts contain no credentials, raw rows, private paths, query
  results, or unrestricted native error text.
- An action refusal is not a successful experiment unless native reread proves
  the column remained and the downstream workload remained healthy.
- An action success is not accepted until native reread proves the column is
  absent and replay is refused.

## Files frozen across CP-01 through CP-04

Only CP-05 may edit these shared integration surfaces:

- `README.md`, `GOAL.md`, `STATUS.md`, `PLAN.md`, and `PROJECT_CONTEXT.md`;
- `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`,
  `docs/DECISIONS.md`, `docs/RISKS.md`,
  `docs/REQUIREMENTS_TRACEABILITY.md`, and `docs/EVIDENCE_LEDGER.md`;
- `src/retirement_conductor/gate.py`, `cli.py`, `agent.py`, and `agent_mcp.py`;
- `.agents/skills/retirement-conductor-agent/` and `.codex/config.toml`;
- existing JSON schemas and existing public evidence;
- `pyproject.toml`, `uv.lock`, and existing shared Make targets.

When a foundation task needs one of those changes, it must record the smallest
required integration hunk in its task-local integration note. It may add a
new isolated Make target with a unique name only when doing so does not modify
an existing target.

## Required foundation report

Each CP-01 through CP-04 branch must finish with:

1. a clean tested commit and exact base commit;
2. frozen input/oracle digest created before the observed product result;
3. exact runtime and source-system versions;
4. exact commands and exit results;
5. retained failure attempts, not only the final successful run;
6. public-safe aggregate evidence with a canonical digest;
7. private/raw evidence location and retention classification;
8. what the result proves and does not prove;
9. an explicit `KEEP`, `SIMPLIFY`, `REMOVE`, `REFRAME`, or `INCONCLUSIVE`
   recommendation;
10. task-local integration notes naming every shared hunk CP-05 requires;
11. `make check` passing on the final branch;
12. disposable services stopped and the worktree clean.

## Stop and reframe conditions

- Stop the real action path if it requires broad SQL execution, production
  credentials, `CASCADE`, or unrecoverable non-disposable data.
- Keep Superset experimental if exact native identity or semantic revalidation
  cannot be reconstructed at gate time.
- Reframe the product if fresh-check CI matches Retirement Conductor on every
  predeclared safety, recovery, and audit measure with materially less state.
- Do not claim prevented breakage if the downstream workload never executed
  successfully before the intervention or its failure is not attributable to
  the exact retired field.
- Do not proceed to CP-05 with fixture-only evidence for a boundary whose brief
  requires live-local native evidence.

## Launch rule

Create four Codex tasks from this planning branch, each in a new worktree, and
paste the corresponding brief as the task. Do not launch CP-05 yet. When all
four foundation tasks finish, inspect and integrate their commits from a fresh
worktree based on this planning branch.
