# Retirement Workbench

The Workbench is the focused operator and demo surface for one Retirement
Conductor campaign. It is not a dashboard, another policy engine, or an
authorization interface. It reads the same digest-verified manifest and event
history as the CLI, then reveals only the current decision, exact cause,
campaign stage, a focused lineage fragment, and one next action.

## What the interface can do

- inspect one campaign selected when the local API starts;
- show Consumers, Change, Evidence, and Activity as separate focused views;
- run DataHub inventory or fresh reconciliation when the operator explicitly
  enables actions;
- refresh from canonical state after the operation completes.

It cannot record human authorization, apply a Git/dbt plan, accept native
validation, issue a Retirement Lease, or execute the producer gate. Those
boundaries remain in the existing CLI/MCP runtime.

## Start a real local campaign view

Start the loopback API in one terminal. Omit `--allow-actions` for an entirely
read-only session.

```bash
retirement-conductor workbench serve \
  --campaign "$CAMPAIGN_ID" \
  --store .retirement-conductor/campaigns.sqlite \
  --writer-id local-operator \
  --artifact-dir .retirement-conductor/artifacts \
  --origin http://localhost:3000 \
  --allow-actions
```

Start the existing site in another terminal, then open
`http://localhost:3000/workbench`.

```bash
npm --prefix site run dev
```

The API refuses any non-loopback bind or browser origin. Runtime actions also
require the browser request's explicit action confirmation header to match the
requested operation. A successful HTTP response is still not retirement
authorization; the canonical campaign decision and producer gate remain the
authority.

## Recorded public evidence

When no local API is available, the public route shows a clearly labeled
recorded view generated from the retained 18-event agent campaign. It is useful
for review and presentation but cannot mutate anything. Its manifest digest is
visible in Evidence, and the committed JSON is
`site/public/workbench-recorded.json`.

When the retained private run is locally available, regenerate that projection
with:

```bash
uv run python scripts/export_workbench_view.py \
  --store .retirement-conductor/agent-full-run/run-c8eccc140033/campaigns.sqlite \
  --writer-id agent-demo-writer-c8eccc140033 \
  --campaign ret-orders-agent-c8eccc140033 \
  --output site/public/workbench-recorded.json
```

The exporter verifies the store, manifest digest, replayed state, and exact
event-history binding before writing the view.

## Three-minute demo role

Use the Workbench as the visual narrative anchor, not the entire demo:

1. start on the real campaign decision and focused lineage;
2. switch briefly to Codex for DataHub inspection and the exact migration plan;
3. show the terminal only for the external human authorization boundary and
   native dbt/CI proof;
4. return to the Workbench for fresh reconciliation and the visible reversal;
5. finish in Evidence or the separate Evidence & Trust Center for provenance.

This keeps the product legible while still proving that the visually polished
surface is backed by real tools and native execution.
