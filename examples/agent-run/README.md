# Full agent run evidence

This bundle is the concrete artifact trail from one real Retirement Conductor
agent run over disposable local DataHub and Git/dbt systems.

The product agent inspected DataHub, created campaign `ret-orders-agent-1930ce52b2a7`, planned
the exact one-file migration in `migration.patch`, and stopped at the human
authorization boundary. After the user directed the outer operator to record
that authorization, the product agent applied the change, ran dbt-native
validation, reconciled fresh evidence, published and read back the DataHub
summary, issued a short-lived Retirement Lease, and executed only a harmless
local sentinel.

A newly injected Spark consumer then caused the same campaign to reverse from
`READY_TO_RETIRE` to `UNSAFE`. No second lease was issued and the gate was not
called again.

## Inspect in order

1. `migration.patch` — the exact dbt change.
2. `change-receipt.json` — native validation and receipt binding.
3. `retirement-lease.json` — the short-lived manifest-bound producer lease.
4. `readiness-reversal.json` — the late consumer and stable refusal codes.
5. `agent-transcript.md` — public-safe stage-by-stage model conclusions.
6. `../../artifacts/public/agent/full-run.json` — the complete digest-bound
   orchestration summary.

## Evidence boundary

This is a user-directed author/operator run, not the independent operator
observation required by RC-018. It used disposable local systems and did not
mutate a production warehouse.
