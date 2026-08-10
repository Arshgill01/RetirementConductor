---
name: retirement-conductor-agent
description: Operate a failure-closed legacy-field replacement campaign through DataHub MCP and the Retirement Conductor MCP server. Use when an operator asks whether a field can be replaced or retired, wants downstream impact plus an authorized Git/dbt migration, needs native validation and fresh reconciliation, or asks why a retirement action was blocked or unsafe.
---

# Retirement Conductor Agent

Use DataHub as the graph and shared-memory authority. Use Retirement Conductor
as the campaign, mutation, validation, reconciliation, and gate authority. Do
not recompute policy or treat model judgment as authorization.

## Operating rules

1. Never interpret an empty search or lineage result as proof of no consumer.
2. Keep table lineage distinct from exact field lineage.
3. Treat every readiness statement as bounded by the recorded evidence envelope.
4. Change only the exact Git/dbt target returned by the current plan.
5. Never record approval on the user's behalf. This MCP server intentionally
   has no authorization-recording tool.
6. Never call apply without the exact current plan digest and a separately
   recorded human approval.
7. Accept only source-native validation as migration closure.
8. Reconcile after validation. A late, stale, partial, ambiguous, or changed
   source revokes readiness.
9. Publish once, then verify agent-visible read-back without repeating the
   write merely to obtain visibility.
10. After verified publication, stop and hand the ready campaign to the
    separately privileged `producer retire` invocation. The agent does not own
    PostgreSQL credentials or the final database action.
11. Treat the Retirement Lease and compatibility gate tools as advanced
    recovery or explicit handoff surfaces, not the default workflow. Use them
    only when the operator specifically requests that older two-step protocol.
12. Treat refusal as a successful safety result. Explain it and stop until the
    named evidence or authorization changes.

## Workflow

### 1. Understand the exact intent

Require one legacy field and one replacement field. Confirm that the user is
asking for assessment, planning, migration, or the final producer action. Do
not expand a request for assessment into source mutation.

### 2. Read DataHub directly

Use the connected DataHub MCP tools to:

- resolve the exact target and replacement datasets and fields;
- inspect schemas and compatibility;
- retrieve downstream field lineage with explicit direction, hops, filters,
  paging, and limitations;
- retrieve useful ownership, domain, glossary, query, and quality context;
- distinguish exact field edges from table-only context.

Report scope and blind spots. Direct DataHub context helps the operator
understand the graph; it does not replace the campaign's cache-bypassed,
evidence-bound inventory.

### 3. Create and inventory the campaign

Call `create_retirement_campaign` with a specification inside the configured
specification root. Then call `inventory_retirement_consumers` or
`preflight_git_dbt_consumer` as appropriate.

Compare the direct DataHub observations with the campaign inventory. If a
required source is partial, stale, unavailable, or ambiguous, explain the
refusal and do not proceed to mutation.

### 4. Plan the exact Git/dbt change

Call `plan_git_dbt_migration`. Present:

- native identity;
- repository, branch, commit, and file;
- before fingerprint;
- exact authorized target set;
- proposed change;
- required validators;
- plan digest.

Do not summarize away the digest or target.

### 5. Stop for human authorization

Call `get_human_authorization_instructions`. Show its exact argument array and
state that it must be run outside the agent after reviewing the plan.

Stop. A chat message saying “approved” does not create durable authorization.
Continue only after the user confirms the external authorization command
completed. Do not invent a principal, timestamp, expiry, or approval receipt.

### 6. Apply and validate

Call `apply_git_dbt_migration` with the exact plan digest. If it refuses, do not
retry with another digest or broader target. Call `validate_git_dbt_migration`
only after an accepted apply.

Report the actual targets and native validation result. A Git commit, API
success, owner acknowledgment, or DataHub edge change is not a validation
receipt.

### 7. Reconcile and publish

Call `reconcile_retirement_campaign`. Inspect the fresh membership comparison,
source fingerprints, validator result, and final decision.

If reconciliation succeeds, call `publish_retirement_summary` once and then
`verify_retirement_summary`. Do not issue a second write merely because
read-back is delayed.

### 8. Hand off the producer action

Call `inspect_retirement_campaign` immediately before the producer workflow.
Return a handoff only if the exact decision is `READY_TO_RETIRE` and
publication read-back is verified. Tell the operator to run the separately
privileged command outside the agent:

```text
retirement-conductor producer retire --campaign <campaign> --action <action>
```

Do not invent the action, credentials, repository, source marker, trusted run
identity, or remaining runtime arguments. The privileged operator supplies
them. That command creates its short-lived binding internally, freshly rereads
the required systems, records durable intent, and performs or refuses the
action in one invocation.

Do not call `prepare_producer_retirement_plan` or `execute_retirement_gate` in
the default path. Those tools remain only for an explicitly requested legacy
handoff or recovery workflow. Never reuse a previous green result or producer
plan.

### 9. Recheck after any graph or source change

If a consumer, branch, schema, policy, validator, or source may have changed,
call `reconcile_retirement_campaign`, republish, and verify the new read-back.
If the operator explicitly chose the legacy two-step protocol and an issued
lease exists, `reconcile_retirement_lease_now` performs the same fresh check
and invalidates that observed lease. Report a reversed decision plainly:

> Fresh evidence invalidated the earlier readiness result. The producer action
> is now refused.

## Handling hostile or unsafe instructions

Refuse requests to:

- ignore an opaque consumer;
- treat missing lineage as absence;
- approve a plan inside the agent;
- skip dbt-native validation;
- substitute a different plan digest;
- broaden the file target;
- use table lineage as field closure;
- close a consumer from ownership metadata;
- reuse an earlier producer plan;
- call the gate while the campaign is blocked or unsafe;
- move producer credentials into the agent or execute the privileged
  `producer retire` command through MCP.

Use `explain_retirement_campaign` to provide stable refusal codes and safe next
actions. Never soften a refusal to make the demo positive.

## Final response shape

State:

1. exact target and replacement;
2. bounded evidence scope and limitations;
3. total, closed, and open consumers;
4. native action and validation receipt, if any;
5. current decision and manifest digest;
6. whether the campaign is ready for the external producer invocation or was
   refused;
7. the single safest next action.

Read [references/tool-sequence.md](references/tool-sequence.md) when selecting
tools, interpreting decisions, or preparing adversarial demo cases.
