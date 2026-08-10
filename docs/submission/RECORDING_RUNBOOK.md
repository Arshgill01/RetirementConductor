# Recording runbook

This is the production checklist for the three-minute Devpost video. The
finished edit may use cuts, zooms, and time compression. It must not imply that
reading a retained artifact performed the original action.

## Recording surfaces

Prepare five surfaces in this order:

1. **Opening deck:** `/pitch`, full screen, browser chrome hidden.
2. **Codex:** one clean task with only the prompt and product tool activity
   visible.
3. **GitHub:** the public one-file PR and its passing `semantic-dbt` check.
4. **Terminal:** the definitive producer command and inspected CP-05 outcomes.
5. **Workbench:** the overview and Evidence view.

Use 1920×1080 or 2560×1440 at 100% browser zoom. Keep the cursor still unless
it is showing the next action. Do not show notification badges, tokens, home
paths, environment dumps, raw traces, Docker logs, or long JSON digests.

## Opening deck controls

- Right arrow, Page Down, or Space: next slide.
- Left arrow or Page Up: previous slide.
- Home / End: first / last slide.
- `H`: hide the controls before recording.
- `?slide=1`, `?slide=2`, or `?slide=3`: open a specific slide directly.

The opening should take 22 seconds. Do not add an architecture slide. The live
workflow is the architecture.

## Codex prompt

Start a new task from the repository root after the project skill, Retirement
Conductor MCP, and DataHub MCP are connected to the prepared disposable demo
environment.

Use this exact first prompt:

```text
Use $retirement-conductor-agent to replace
retirement_conductor.analytics.commerce.orders_isolated.legacy_status with
order_status. Inspect DataHub directly, create one campaign, inventory the
complete bounded evidence, and plan the smallest safe Git/dbt migration.
Stop at the external human-authorization boundary. Use DataHub MCP and the
Retirement Conductor MCP; do not use shell or edit files directly. Show the
exact target, validators, evidence limitations, and plan digest.
```

After running the returned authorization command in the separate operator
terminal, use:

```text
The exact plan authorization has now been recorded outside the agent. Continue
through apply, native dbt validation, fresh reconciliation, DataHub publication,
and read-back verification. Stop after the final campaign inspection. Do not
prepare a Retirement Lease, call the compatibility gate, or attempt the
privileged producer action.
```

If Codex uses shell, edits the file directly, authorizes itself, skips native
validation, or calls the legacy lease/gate path, discard the take. Do not
explain the mistake in the final video.

## Producer footage

The producer action is a separate proof boundary. Capture a fresh disposable
CP-05 run before editing:

```bash
uv run python scripts/run_definitive_consequential.py run
uv run python scripts/run_definitive_consequential.py verify
```

The run is intentionally much longer than the video. Record the real command
and final results, then cut indexing, container startup, and native workload
waits. Never point it at production.

For clean, legible result frames, inspect only the fields used in narration:

```bash
jq '{result, action, replacement_workload_after, replay}' \
  artifacts/public/definitive-consequential-run/retirement-conductor-clean.json

jq '{result, decision, refusal_code, destructive_statements_committed, schema_after}' \
  artifacts/public/definitive-consequential-run/retirement-conductor-late.json

jq '{result, destructive_statements_committed, legacy_workload_after}' \
  artifacts/public/definitive-consequential-run/point-in-time-static.json
```

Say “the captured run produced this evidence” while these are visible. Do not
say that `jq` executed the migration.

## Public links to preload

- Workbench: <https://retirement-conductor.arshgill01.chatgpt.site/workbench>
- Codex migration PR:
  <https://github.com/Arshgill01/retirement-conductor-definitive-acceptance/pull/1>
- Source repository: <https://github.com/Arshgill01/RetirementConductor>

Open every page before recording. Collapse unrelated GitHub navigation and
zoom the one-file diff and passing check until both are legible.

## Take acceptance

Reject the finished cut unless all are true:

- total duration is under 3:00;
- DataHub is named and visibly changes the decision;
- Codex calls product tools rather than silently editing source;
- human authorization is visibly external;
- one native change and native validation are shown;
- the PostgreSQL drop is explicitly real and disposable;
- late evidence causes zero destructive statements;
- the failed Spark control is shown as consequence, not as product behavior;
- the Workbench is not presented as a privileged execution surface;
- no claim suggests universal graph completeness or superiority over competent
  fresh CI;
- captions remain readable at 1080p;
- no credentials, tokens, private paths, or raw sensitive evidence appear.

## Fallback hierarchy

1. **Preferred:** fresh Codex consumer run plus fresh CP-05 producer run.
2. **Acceptable:** inspected retained Codex run plus fresh CP-05 producer run,
   explicitly described as two verified runs.
3. **Emergency:** public agent transcript, public PR, CP-05 public evidence,
   and Workbench. Label every retained artifact as recorded evidence.

Never substitute a scripted fake terminal or hard-coded “ready → unsafe”
animation for a failed live take.
