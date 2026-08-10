# CP-03 — realistic alternative ablation v2

## Objective

Build a fair, frozen, executable comparison between:

1. point-in-time impact analysis plus native CI and approval;
2. a competent failure-closed fresh DataHub pre-action CI check;
3. Retirement Conductor's campaign, Retirement Lease, and one-use gate.

The experiment must determine whether Retirement Conductor produces a
materially better result than the realistic alternative. It must not begin
with that conclusion.

## Product question

After identical inventory, migration, native validation, approval, drift, and
producer action, does the campaign protocol prevent more unsafe actions,
preserve more usable recovery state, or produce a more complete causal audit
than a small fresh-check CI workflow?

## Fairness contract

All arms receive the same:

- initial DataHub graph and pagination boundary;
- producer schema and deterministic data;
- known Git/dbt and Superset consumer changes where the scenario requires
  them;
- native validation outputs;
- human approval scope and time;
- late-consumer or source-drift intervention;
- maximum evidence age and trusted clock;
- exact PostgreSQL action from CP-01 during final integration;
- downstream outcome probe from CP-04 during final integration.

The fresh-check CI arm must be a serious baseline. It must:

- rerun complete paged DataHub inventory immediately before action;
- fail closed on unavailable, partial, stale, unauthorized, or ambiguous
  evidence;
- compare exact consumer membership with its approved snapshot;
- reread the producer schema/source fingerprint;
- call the same native action boundary only after its checks pass;
- record its own safe report and exit code.

It may remain stateless beyond one CI run because that is the architecture
under evaluation. Do not intentionally omit safety checks that a competent
team would obviously implement.

The point-in-time arm freezes its initial green report, native CI result, and
approval and performs no automatic refresh. That is a defined static contract,
not a claim about a named vendor.

## Frozen scenario matrix

Freeze the inputs and independent expected properties before executing any
arm. Include at least:

| Scenario | Required observation |
|---|---|
| No drift clean control | Every safe arm permits exactly one real action; no false refusal. |
| Late exact-field consumer | Static authority proceeds; fresh CI and Retirement Conductor should detect and block. |
| Late table-only/ambiguous edge | Failure-closed arms refuse rather than infer field safety. |
| DataHub unavailable at action time | Fresh CI and Retirement Conductor refuse; static behavior is recorded honestly. |
| Incomplete pagination | Failure-closed arms refuse. |
| Producer schema drift | Fresh CI and Retirement Conductor refuse before action. |
| Git/dbt source or validation drift | Measure whether each arm binds and invalidates the earlier validation. |
| Superset native drift | Measure after CP-02 integration; no arm may trust stale BI validation. |
| Approval expired or scope changed | Measure whether stale approval can still authorize action. |
| Action replay | Exactly one committed drop; every later use refuses or proves already applied. |
| Crash before action | Retry/recovery must not create a duplicate action. |
| Lost response after action intent | Native reread must resolve or retain outcome unknown; no blind retry. |
| Publication/audit artifact unavailable | Distinguish action safety from ability to reconstruct and explain the decision. |

The foundation branch may use protocol fakes for the action and workload, but
must leave explicit adapters for CP-01 and CP-04. CP-05 reruns the decisive
clean, late-consumer, replay, and lost-response cases over live native systems.

## Independent oracle

The oracle must not import Retirement Conductor policy, gate, baseline
implementation, or scenario runner. It should state observable facts rather
than desired product labels:

- whether the producer action was safe under the frozen graph and source;
- whether a destructive statement may execute;
- expected maximum committed action count;
- expected final column presence;
- expected downstream workload health;
- whether prior approval should remain operationally reusable;
- whether the run must retain an unresolved outcome;
- minimum audit fields required to reconstruct why the action proceeded or
  stopped.

## Measures

Report per arm and scenario:

- unsafe committed producer actions;
- false refusals in clean controls;
- destructive statements attempted and committed;
- stale approval or green-artifact reuse;
- duplicate/replayed action attempts;
- outcome-unknown states resolved correctly;
- manual interventions required for safe recovery;
- evidence sources reread;
- exact reason an operator can recover from the final artifact;
- presence of graph, source, approval, validation, action, and outcome
  bindings in the final audit record;
- elapsed action-path time as descriptive evidence only, not a winning metric.

Do not collapse these into an unreviewable weighted score. Publish the matrix
and a small predeclared decision rule.

## Decision rule

Classify the final result as exactly one:

- `MATERIALLY_BETTER` — Retirement Conductor prevents an unsafe action or
  stale/replayed authority that fresh CI permits, without a clean-control
  regression;
- `SAFETY_EQUIVALENT_PROTOCOL_ADVANTAGE` — both prevent unsafe actions, but
  Retirement Conductor demonstrably improves one-use authority, interruption
  recovery, or causal audit reconstruction;
- `NO_MATERIAL_ADVANTAGE` — fresh CI matches the predeclared safety, recovery,
  and audit properties with less persistent machinery;
- `WORSE` — Retirement Conductor causes a safety failure or material clean
  control regression absent from the baseline;
- `INCONCLUSIVE` — the identical live experiment cannot be completed.

The decision rule and thresholds must be frozen before live outputs are
observed.

## Evidence

Create:

```text
fixtures/realistic-alternative-ablation-v2/FROZEN.json
artifacts/public/realistic-alternative-ablation-v2/
docs/plans/realistic-alternative-ablation-v2-report.md
docs/plans/integration-notes-realistic-ablation-v2.md
```

Public evidence must contain the frozen digest, per-arm matrix, failure
attempts, exact baseline capability statement, decision classification,
limitations, and canonical self-digest. It must not claim the baseline
represents DataHub or another vendor product.

## Owned implementation

Prefer task-local runner and evaluator modules under `scripts/` and focused
tests. Do not modify product policy, gate, MCP, skill, existing lease-value
evidence, or canonical documentation.

## Validation

- Verify the frozen corpus digest independently.
- Prove the evaluator rejects missing arms, changed inputs, unmatched native
  actions, post-hoc oracle edits, and an intentionally biased baseline.
- Run the complete foundation matrix.
- Inspect public and retained raw evidence.
- Run `make check`.

## Completion recommendation

Report the exact decision classification plus `KEEP`, `SIMPLIFY`, `REFRAME`,
or `REMOVE` for the current campaign/lease/gate complexity. An inconclusive
run cannot become a positive product recommendation.
