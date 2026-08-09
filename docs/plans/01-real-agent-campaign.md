# WS-01 — real model-driven campaign

## Objective

Produce a raw, inspectable trace in which the connected model operates the
actual Retirement Conductor tools over disposable live-local DataHub and
Git/dbt state. The trace must show useful model decisions, a real native
change, deterministic enforcement, write-back, and later refusal. It must not
be a model narrating a prewritten `READY_TO_RETIRE` or `UNSAFE` fixture.

This workstream is already active on
`codex/agent-demo-and-datahub-contributions`. This brief constrains its
acceptance; it is not authorization for another agent to edit the same files.

## Required run

1. Start the pinned disposable DataHub Core and exact Git/dbt workspace.
2. Create or ingest the target and replacement fields plus at least one exact
   field-level Git/dbt consumer.
3. Give the model a human request naming the intended replacement, not a
   campaign decision or expected tool order.
4. Require direct DataHub MCP reads for exact identity, schema compatibility,
   downstream context, and limitations.
5. Let the model create or select the exact campaign specification and invoke
   inventory, preflight, and plan tools.
6. Stop at the human authorization boundary. Record the exact plan digest and
   approved target outside the agent.
7. Resume the same trace. Apply exactly one authorized target and run the
   declared dbt parse, seed, build, test, and semantic parity operations.
8. Reconcile fresh DataHub evidence, publish once, and verify read-back.
9. Reach `READY_TO_RETIRE` only if the canonical policy permits it, then issue
   and harmlessly consume one short-lived producer plan.
10. Add a genuinely new consumer through DataHub ingestion or supported
    metadata APIs. Do not append a campaign event or edit a manifest.
11. Reconcile the same campaign again. The model must identify the new
    consumer, explain the changed decision, and refuse another producer action.

## Model behavior that must be visible

- It resolves which exact DataHub entities the human meant.
- It chooses context tools based on observations rather than a prompt that
  dictates exactly two tool names.
- It notices pagination, freshness, and table-versus-field limitations.
- It explains the proposed native target and semantic proof before approval.
- It stops for external authorization.
- It diagnoses any tool refusal instead of bypassing it.
- It distinguishes successful native validation from final readiness.
- It recognizes that later evidence invalidates the previous conclusion.

No raw chain-of-thought is required or desired. Retain structured tool calls,
typed observations, canonical results, and the model's concise operational
explanations.

## Anti-hardcoding checks

- The acceptance prompt does not state the expected final decision.
- The model does not receive a preselected blocker code.
- Campaign identifiers come from tool output or a freshly created campaign,
  not a retained public artifact.
- Source and replacement URNs are resolved against the running DataHub.
- The repository diff is inspected after apply.
- dbt output and receipt artifacts are reread rather than trusted from exit
  status alone.
- The late consumer is visible in DataHub before Retirement Conductor sees it.
- The second decision is rebuilt from fresh canonical state.
- The producer action count is inspected before and after revocation.

## Public evidence

Publish a redacted summary containing:

- repository and behavior commits;
- model host and version;
- DataHub Core and MCP versions;
- exact ordered DataHub and Retirement Conductor tool names;
- source evidence and pagination summaries;
- plan, approval, apply, validation, reconciliation, publication, manifest,
  producer-plan, and gate digests;
- before/after consumer counts and decisions;
- producer action count;
- raw-trace digest and private retention statement;
- limitations and explicit non-claims.

Keep raw traces ignored because they may contain local paths or private
runtime context. Run secret and public-artifact checks over the promoted
summary.

## Acceptance commands

At minimum:

```bash
make check
make test-end-to-end
make phase04-evidence
make agent-acceptance
```

Add one command for the new full model-driven trace if it is separate from the
existing late-state acceptance. Inspect every generated artifact.

## Stop conditions

Do not promote the trace as complete if:

- the model only reads a retained decision;
- a script directly changes campaign state to create the reversal;
- authorization occurs inside the model tool surface;
- validation is simulated or replaced with a command-success claim;
- DataHub publication is not read back;
- the late consumer is not first observable in DataHub;
- the producer plan is not actually invalidated or refused;
- the trace requires an undocumented manual correction.
