# WS-03 integration notes

## Branch contract

- Branch: `codex/continuous-retirement-lease`
- Base: `6adb47f50bd741eb963449ca4b1c470f3ede64cd`
- Workstream brief: `docs/plans/03-continuous-reconciliation.md`

This branch owns the new watcher, watch receipt schema, lease projection,
focused tests, continuous-reconciliation runbook, and live-local evidence
runner. It does not edit `GOAL.md`, `STATUS.md`, `README.md`, `PLAN.md`, product
contracts, architecture, risks, decisions, requirements traceability, the
evidence ledger, or WS-01 agent artifacts.

## Runtime registrations

The narrow CLI registrations add:

- `campaign lease-status` for read-only `ISSUED`, `EXPIRED`, `CONSUMED`, or
  `INVALIDATED` projection from existing canonical records;
- `campaign watch --once` for bounded reconciliation, policy evaluation,
  publication, verification, and a stable result-specific exit code.

The integration owner should expose two MCP tools after rebasing onto the
frozen WS-01 agent contract:

1. a read-only lease-status tool that calls `retirement_lease_status`;
2. a bounded reconcile-now tool that calls `WatchWorkflow.run_once` and
   returns the watch receipt without allowing the model to change scope,
   policy, lease status, or authorization.

No `agent.py`, `agent_mcp.py`, agent acceptance runner, public agent artifact,
or agent demo runbook is modified on this branch. Reapply only those two
minimal registrations during integration and rerun the frozen agent
acceptance.

## Shared-file merge notes

- `cli.py`: retain the two subcommands and dispatch only.
- `store.py`: retain re-entrant use of the existing file lock,
  `operation_lock`, integrity-checked gate-plan listing, and the observation
  event helper.
- `events.py` and `campaign-event-v1.schema.json`: retain the no-authority
  `WATCH_OBSERVATION_RECORDED` event.
- `publication.py`: retain the shared write-once/resumable publication
  workflow used by both existing commands and the watcher.
- `schemas.py`: retain the `watch-receipt` registration.

Do not resolve these files by taking either branch wholesale. Reapply the
minimal hunks to the post-WS-01/WS-02 files, then run focused tests and
`make check`.

## Live-local acceptance evidence

The acceptance run at repository commit
`734529dfaeb5550c0d94e0d45822b6eaceec3757` produced public-safe evidence in
`artifacts/public/ws03/`:

- acceptance digest:
  `sha256:09b66f9c715d7867ffdadf75c54936a5eb844e42fdc71355d51329ef37a3a5bb`;
- watch receipt digest:
  `sha256:56db58f8c08c547558e0bb032da7ee76b5a03c22bd4ecc41202ab30b254039e7`;
- live DataHub Core v1.6.0 changed the observed decision from
  `READY_TO_RETIRE` to `UNSAFE`, and publication readback verified the changed
  summary;
- the independent `upstreamLineage` aspect reread proved exactly one
  `legacy_status` to late-consumer `order_status` field edge;
- the real Git patch touched only `models/orders_isolated_model.sql`, and
  native `dbt parse + seed + build + test on DuckDB` passed;
- the preserved lease projected from `ISSUED` to `INVALIDATED`; the old plan
  was refused with `GATE_DECISION_NOT_READY` and no producer sentinel;
- removing the late graph edge did not close or validate the observed
  consumer, and the campaign remained `UNSAFE`.

The DataHub MCP field-lineage helper conservatively reports the late asset as
table-only even though the authoritative DataHub aspect exposes the exact
fine-grained edge. The public evidence preserves both observations; readiness
does not depend on upgrading the weaker helper result.

## Controlling-document updates after live acceptance

The integration owner should add RC-020 or the next unused requirement for
continuous fresh observation and lease invalidation, record the watch event
and receipt contracts, add the observed late-consumer evidence to the evidence
ledger, and update R-04, R-12, R-23, R-27, R-34, and R-35 only to the scope
proved by the live-local run.
