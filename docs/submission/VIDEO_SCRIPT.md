# Three-minute recording script — read exactly

Target duration: **2:52–2:58**.

Read only the paragraphs labeled **VOICEOVER — READ EXACTLY**. Everything
labeled **SCREEN — DO NOT READ** is an editing or screen-direction instruction.
Do not improvise, explain tool output, or add a spoken introduction or thank-you.

This is an edited proof assembled from real runs. Record each shot separately
if that is easier; the video does not need to be one uninterrupted screen take.

## Before recording — prepare these exact surfaces

### Browser

Open these tabs in this order:

1. Deck slide 1:
   <https://retirement-conductor.arshgill01.chatgpt.site/pitch?slide=1>
2. New agent-created pull request:
   <https://github.com/Arshgill01/retirement-conductor-definitive-acceptance/pull/2/files>
3. Passing native CI job:
   <https://github.com/Arshgill01/retirement-conductor-definitive-acceptance/actions/runs/31420802937/job/93560781990>
4. Workbench:
   <https://retirement-conductor.arshgill01.chatgpt.site/workbench>

Use 100% zoom. On the deck, press `H` once to hide its controls.

### Codex app

Open the [fresh campaign task](codex://threads/019fecee-651d-7322-afd9-4be22c76e6ff)
through this direct link. It was created through Codex CLI and may not appear in
the sidebar.

Record only these parts of that task:

1. the original user prompt and the real DataHub/MCP tool calls;
2. the final plan beginning **“Stopped at the external human-authorization
   boundary”**;
3. the successful apply and validation calls;
4. the final response beginning **“Fresh reconciliation changed the
   deterministic decision”**.

Do not record the short task-store/environment recovery turn. Do not record the
stale-evidence intermediate response unless you deliberately want a longer
technical cut. The final refreshed reconciliation is the canonical outcome.

### Normal terminal

Open a normal terminal—not another Codex task—at:

```bash
cd /home/arshdeepsingh/work/RetirementConductor-final
```

Create four terminal tabs named `AUTH`, `CLEAN`, `LATE`, and `STATIC`. Run the
corresponding read-only command in each tab before recording so every frame is
already clean and waiting.

**AUTH**

```bash
clear
jq '{campaign_id, principal, plan_digest, targets, authorized_at, expires_at}' \
  .retirement-conductor/video-agent/artifacts/ret-orders-isolated/git-dbt/approval.json
```

**CLEAN**

```bash
clear
jq '{result: .action.result, destructive_statements_committed: .action.destructive_statements_committed, legacy_column_present: .action.legacy_column_present, replacement_column_preserved: .action.replacement_column_preserved, replacement_spark_workload: .replacement_workload_after.outcome, replay: .replay.result}' \
  artifacts/public/definitive-consequential-run/retirement-conductor-clean.json
```

**LATE**

```bash
clear
jq '{result, decision, refusal_code, destructive_statements_committed, legacy_column_present: .schema_after.legacy_column_present}' \
  artifacts/public/definitive-consequential-run/retirement-conductor-late.json
```

**STATIC**

```bash
clear
jq '{result, destructive_statements_committed, legacy_column_present: .schema_after.legacy_column_present, spark_outcome: .legacy_workload_after.outcome, sqlstate: .legacy_workload_after.sqlstate}' \
  artifacts/public/definitive-consequential-run/point-in-time-static.json
```

These commands only display inspected evidence. They do not execute, authorize,
or retry any product action.

---

## 0:00–0:33 — Establish the problem before showing tools

### 0:00–0:11

**SCREEN — DO NOT READ**

- Active app: browser.
- Active tab: deck slide 1.
- Keep the slide completely still.

**VOICEOVER — READ EXACTLY**

> Imagine you own this warehouse table. The replacement field,
> `order_status`, is live. Now you want to delete `legacy_status`. That sounds
> like one SQL statement—until a model, dashboard, or Spark job still reads it.

### 0:11–0:22

**SCREEN — DO NOT READ**

- Press the right arrow once to show deck slide 2.
- Do not move the cursor after the slide changes.

**VOICEOVER — READ EXACTLY**

> In our live scope test, repository search found one consumer. DataHub field
> lineage found thirty-one, across seven complete pages. The hard part is not
> writing `DROP COLUMN`. It is knowing what must move before you run it.

### 0:22–0:33

**SCREEN — DO NOT READ**

- Press the right arrow once to show deck slide 3.
- Hold on the complete workflow shown on the slide.

**VOICEOVER — READ EXACTLY**

> Retirement Conductor is the workflow around that deletion. It finds the
> consumers in DataHub, changes only what it is allowed to change, runs the
> consumer's real tests, checks the graph again, and then deletes the old
> column—or stops.

---

## 0:33–1:22 — Show one real agent-created consumer migration

### 0:33–0:43

**SCREEN — DO NOT READ**

- Cut to the Codex app.
- Show the original user prompt at the top of the fresh task.
- Scroll slowly past the visible DataHub calls: `search`,
  `list_schema_fields`, and `get_lineage`.
- Keep large tool responses collapsed. The tool names must remain legible.

**VOICEOVER — READ EXACTLY**

> Here is one real campaign. Codex is the operator interface, not the safety
> authority. I ask it to move this consumer from `legacy_status` to
> `order_status`.

### 0:43–0:53

**SCREEN — DO NOT READ**

- Stay in the same Codex task.
- Cut or scroll to **Campaign and target** in the first final response.
- Keep these three lines visible: the sole authorized file, the five validators,
  and plan digest `sha256:34f7e1…3008d`.

**VOICEOVER — READ EXACTLY**

> Through DataHub and our MCP server, it identifies the exact D-B-T model and
> proposes a one-file change.

### 0:53–0:59

**SCREEN — DO NOT READ**

- Stay in the Codex task.
- Show the heading **Stopped at the external human-authorization boundary**.
- Make sure `models/orders_isolated_model.sql` and the plan digest are visible.

**VOICEOVER — READ EXACTLY**

> Before changing code, it stops. I review the file, validators, and digest.

### 0:59–1:04

**SCREEN — DO NOT READ**

- Cut to the normal terminal.
- Show the preloaded `AUTH` tab and its durable authorization receipt.
- Do not rerun the expired authorization command.

**VOICEOVER — READ EXACTLY**

> Then I authorize that exact plan outside the agent. The agent cannot approve
> itself.

### 1:04–1:12

**SCREEN — DO NOT READ**

- Cut to the browser tab containing PR number 2 on **Files changed**.
- Center the one-line replacement:
  `legacy_status as normalized_status` → `order_status as normalized_status`.
- Do not show the PR Conversation tab.

**VOICEOVER — READ EXACTLY**

> The same task applies the authorized change. The pull request changes one
> line.

### 1:12–1:17

**SCREEN — DO NOT READ**

- Cut to the browser tab containing the native CI job.
- Keep the green `semantic-dbt` result and successful job steps visible.

**VOICEOVER — READ EXACTLY**

> D-B-T parse, build, test, and semantic checks pass.

### 1:17–1:22

**SCREEN — DO NOT READ**

- Cut back to the Codex app.
- Show only the successful final response beginning **Fresh reconciliation
  changed the deterministic decision**.
- Keep `READY_TO_RETIRE` and `Read-back verified: true` visible.

**VOICEOVER — READ EXACTLY**

> Retirement Conductor checks DataHub again, publishes the result, and reads it
> back for the next operator or agent.

---

## 1:22–2:32 — Prove the database action and the changed answer

### 1:22–1:47

**SCREEN — DO NOT READ**

- Cut to the normal terminal.
- Show the preloaded `CLEAN` tab full-screen.
- Keep all six displayed fields visible; do not scroll.

**VOICEOVER — READ EXACTLY**

> Migrating the consumer is not the finish line. In a separate consequential
> run of the same protocol, a privileged command checks DataHub, native
> validation, approval, and the producer schema again. It executes one real
> PostgreSQL `DROP COLUMN`. The old field is gone, the replacement remains, the
> replacement Spark workload still succeeds, and replay is refused.

### 1:47–1:58

**SCREEN — DO NOT READ**

- Cut to the Workbench in the browser.
- Click the **Retirement Workbench** wordmark if necessary to return to Overview.
- Hold on the `UNSAFE` headline and the broken branch leading to the newly
  observed Spark consumer.

**VOICEOVER — READ EXACTLY**

> Now change one fact. After approval, an ad hoc Spark job appears in DataHub
> still reading `legacy_status`.

### 1:58–2:17

**SCREEN — DO NOT READ**

- Cut to the normal terminal.
- Show the preloaded `LATE` tab full-screen.
- Keep `REFUSED_BEFORE_ACTION`, `UNSAFE`, zero destructive statements, and
  `legacy_column_present: true` visible.

**VOICEOVER — READ EXACTLY**

> Retirement Conductor checks again at execution time. The answer flips to
> unsafe. The final command commits nothing, and the old column stays. That is
> not dashboard theatre.

### 2:17–2:32

**SCREEN — DO NOT READ**

- Cut to the normal terminal's preloaded `STATIC` tab.
- Keep the committed statement, missing legacy column, failed Spark outcome,
  and SQL state `42703` visible.

**VOICEOVER — READ EXACTLY**

> In the matched static-signoff control, nobody rechecks the graph. The column
> is dropped, and the same Spark workload fails with SQL state
> four-two-seven-zero-three: column does not exist. Retirement Conductor
> prevents that exact failure.

---

## 2:32–2:57 — Make the evidence readable and close

### 2:32–2:42

**SCREEN — DO NOT READ**

- Cut back to the Workbench.
- Click **Evidence** in the bottom navigation.
- Show the DataHub source, captured time, bounded coverage, and freshness.

**VOICEOVER — READ EXACTLY**

> The Workbench makes the consequential campaign readable: the consumers, exact
> change, native tests, evidence freshness, and why the decision changed.

### 2:42–2:57

**SCREEN — DO NOT READ**

- Click the **Retirement Workbench** wordmark to return to Overview.
- Hold on the `UNSAFE` decision and broken Spark branch until the video ends.
- Do not move the cursor. Do not add another slide or spoken thank-you.

**VOICEOVER — READ EXACTLY**

> DataHub is not decoration, and the model does not decide safety. Retirement
> Conductor turns changing context into a verified database change—or a safe
> refusal.
