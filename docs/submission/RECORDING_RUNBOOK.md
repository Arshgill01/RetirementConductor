# Recording runbook

This is the production checklist for the three-minute Devpost video. The
finished edit may use cuts, zooms, and time compression. It must not imply that
reading a retained artifact performed the original action.

## What to open

You do not need two Codex instances. Prepare these windows before recording:

1. **Browser tab 1 — deck:**
   <https://retirement-conductor.arshgill01.chatgpt.site/pitch>
2. **Codex app — one task:** use the retained real agent task for the safest
   take. Start a fresh task only if the disposable DataHub and campaign runtime
   have already been prepared. The repository for a fresh task is the clean
   main worktree at `/home/arshdeepsingh/work/RetirementConductor-final`.
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

The opening should take 22 seconds. Do not add an architecture slide. The live
workflow is the architecture.

## Codex prompt

**Recommended under deadline:** reopen the completed real Codex task that
created the public migration PR and record its prompt, product tool calls,
authorization stop, and final result. That is real evidence and avoids gambling
the take on cold DataHub or MCP setup. It is the earlier task whose final output
begins, "Done. The Retirement Conductor agent—not me—completed a real end-to-end
run," and links to `examples/agent-run/agent-transcript.md`.

If the disposable demo runtime is already running and you deliberately choose a
fresh run, start exactly one new Codex task from the clean main worktree. Paste
the following into that task:

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

1. `0:00–0:22` — deck slides 1–3.
2. `0:22–0:43` — Codex prompt, DataHub/MCP tool calls, exact one-file plan.
3. `0:43–0:55` — authorization stop, then the normal terminal command.
4. `0:55–1:18` — GitHub PR and green CI, then Codex publication/read-back.
5. `1:18–1:43` — clean producer command and filtered clean evidence.
6. `1:43–2:09` — late Spark consumer and `UNSAFE` reconciliation.
7. `2:09–2:32` — refusal beside the static Spark failure control.
8. `2:32–2:57` — Workbench Overview, one click to Evidence, hold the final
   unsafe frame for two seconds.

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

1. **Recommended now:** inspected retained Codex run plus fresh CP-05 producer
   run, explicitly described as two verified runs.
2. **Fresh:** fresh Codex consumer run plus fresh CP-05 producer run, but only
   after the disposable runtime has been prepared and dry-run once.
3. **Fallback:** public agent transcript, public PR, CP-05 public evidence,
   and Workbench. Label every retained artifact as recorded evidence.

Never substitute a scripted fake terminal or hard-coded “ready → unsafe”
animation for a failed live take.
