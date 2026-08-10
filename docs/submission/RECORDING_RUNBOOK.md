# Recording runbook

This is the production checklist for the three-minute Devpost video. The
finished edit may use cuts, zooms, and time compression. It must not imply that
reading a retained artifact performed the original action.

## What to open

You do not need two Codex instances. Prepare these windows before recording:

1. **Browser tab 1 — deck:**
   <https://retirement-conductor.arshgill01.chatgpt.site/pitch>
2. **Codex app — one task:** use the
   [fresh judge-visible task](codex://threads/019fecee-651d-7322-afd9-4be22c76e6ff).
   It runs from the
   clean main worktree at `/home/arshdeepsingh/work/RetirementConductor-final`
   against the prepared disposable DataHub and campaign runtime. This task was
   created through Codex CLI, so it may not appear in the normal sidebar index;
   open it through this direct task link.
3. **Normal terminal — operator:** one shell tab opened at that same repository
   root. This is not another Codex CLI or another Codex task.
4. **Browser tab 2 — GitHub:** preload the public one-file pull request and its
   passing check.
5. **Browser tab 3 — Workbench:** preload `/workbench`, first on Overview and
   then ready to open Evidence.

Record one dominant full-screen surface at a time. Do not put all five windows
side by side. The final video is an edited sequence of short clips, not one
continuous desktop performance.

Use 1920×1080 or 2560×1440 at 100% browser zoom. Keep the cursor still unless
it is showing the next action. Do not show notification badges, tokens, home
paths, environment dumps, raw traces, Docker logs, or long JSON digests.

## Opening deck controls

- Right arrow, Page Down, or Space: next slide.
- Left arrow or Page Up: previous slide.
- Home / End: first / last slide.
- `H`: hide the controls before recording.
- `?slide=1`, `?slide=2`, or `?slide=3`: open a specific slide directly.

The opening should take about 33 seconds. It must establish the proposed
database deletion, the downstream failure risk, DataHub's expanded evidence,
and the product definition before the first tool call. Do not add an
architecture slide. The live workflow is the architecture.

## Codex prompt

The disposable runtime has been prepared for the fresh task linked above. Its
first turn uses this exact prompt:

Use this exact first prompt:

```text
Use $retirement-conductor-agent to replace
retirement_conductor.analytics.commerce.orders_isolated.legacy_status with
order_status. Inspect DataHub directly, create one campaign from
git-dbt-isolated-live.yaml, inventory the complete bounded evidence, and plan
the smallest safe Git/dbt migration.
Stop at the external human-authorization boundary. Use DataHub MCP and the
Retirement Conductor MCP; do not use shell or edit files directly. Show the
exact target, validators, evidence limitations, and plan digest.
```

Codex should stop and return an exact authorization command. Copy that command
into the **normal operator terminal** opened at the repository root. Do not
open another Codex task and do not paste the command into Codex.

After the terminal command succeeds, return to the **same Codex task** and paste:

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

The second prompt is therefore not a second agent. The boundary is:

```text
same Codex task: inspect and plan
  → normal terminal: record one human authorization
  → same Codex task: apply, validate, reconcile, publish, stop
```

## Producer footage

Run producer commands in the **normal terminal**, from:

```bash
cd /home/arshdeepsingh/work/RetirementConductor-final
```

This is a separate proof boundary from the Codex task. If you want a fresh
disposable CP-05 run, run it before recording the polished result frames:

```bash
uv run python scripts/run_definitive_consequential.py run
uv run python scripts/run_definitive_consequential.py verify
```

The run is intentionally much longer than the video and may update generated
evidence files. Record the real command and its final result, then cut indexing,
container startup, and native workload waits. Never point it at production. If
time is tight, use the already inspected CP-05 artifacts and say, "This captured
run produced this evidence." Do not pretend reading an artifact is a fresh run.

For clean, legible result frames, inspect only the fields used in narration:

```bash
jq '{result, action, replacement_workload_after, replay}' \
  artifacts/public/definitive-consequential-run/retirement-conductor-clean.json

jq '{result, decision, refusal_code, destructive_statements_committed, schema_after}' \
  artifacts/public/definitive-consequential-run/retirement-conductor-late.json

jq '{result, destructive_statements_committed, legacy_workload_after}' \
  artifacts/public/definitive-consequential-run/point-in-time-static.json
```

`jq` is only a JSON viewer. These commands read the already-produced evidence
files and print five or six useful fields so the judge is not staring at a wall
of JSON. They do not run, change, authorize, or retry anything.

Say “the captured run produced this evidence” while these are visible. Do not
say that `jq` executed the migration.

## Exact edit order

Use these cuts; the times match `VIDEO_SCRIPT.md`:

1. `0:00–0:33` — deck slides 1–3: deletion, danger, product.
2. `0:33–0:53` — Codex prompt, DataHub/MCP tool calls, exact one-file plan.
3. `0:53–1:04` — authorization stop, then the normal terminal command.
4. `1:04–1:22` — GitHub one-line diff and green CI, then publication/read-back.
5. `1:22–1:47` — clean producer command and filtered clean evidence.
6. `1:47–2:08` — late Spark consumer and `UNSAFE` reconciliation.
7. `2:08–2:32` — refusal beside the static Spark failure control.
8. `2:32–2:57` — Workbench Overview, one click to Evidence, hold the final
   unsafe frame for two seconds.

## Public links to preload

- Workbench: <https://retirement-conductor.arshgill01.chatgpt.site/workbench>
- Codex migration PR, one-line diff:
  <https://github.com/Arshgill01/retirement-conductor-definitive-acceptance/pull/2/files>
- Native semantic-dbt job:
  <https://github.com/Arshgill01/retirement-conductor-definitive-acceptance/actions/runs/31420802937/job/93560781990>
- Source repository: <https://github.com/Arshgill01/RetirementConductor>

Open every page before recording. The pull request's Conversation page is not
the useful frame: it mostly shows the check summary. Record the **Files
changed** URL for the exact one-line replacement, then cut to the Actions job
for the native validation commands and successful result.

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

1. **Recommended now:** the linked fresh Codex consumer task plus the inspected
   CP-05 producer evidence, explicitly described as two verified runs.
2. **Fresh producer:** the linked fresh Codex task plus a fresh CP-05 producer
   run when the extra runtime is available.
3. **Fallback:** public agent transcript, public PR, CP-05 public evidence,
   and Workbench. Label every retained artifact as recorded evidence.

Never substitute a scripted fake terminal or hard-coded “ready → unsafe”
animation for a failed live take.
