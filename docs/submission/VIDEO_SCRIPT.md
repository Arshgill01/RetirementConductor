# Three-minute video script

Target duration: **2:52–2:58**. This version intentionally spends the first 33
seconds establishing the operator, the proposed database change, and the
failure it can cause. Speak naturally and quickly; do not rush the final
reversal.

The video is an edited proof, not one uninterrupted terminal recording. Every
result shown must come from a real inspected run, but setup, indexing, container
startup, and validator waits should be cut.

## 0:00–0:33 — The incident and the product

### 0:00–0:11 — What the team wants to do

**Screen:** pitch slide 1.

**Say:**

> Imagine you own this warehouse table. The replacement field,
> `order_status`, is live. Now you want to delete `legacy_status`. That sounds
> like one SQL statement—until a model, dashboard, or Spark job still reads it.

### 0:11–0:22 — Why ordinary repository search is insufficient

**Screen:** pitch slide 2.

**Say:**

> In our live scope test, repository search found one consumer. DataHub field
> lineage found thirty-one, across seven complete pages. The hard part is not
> writing `DROP COLUMN`. It is knowing what must move before you run it.

### 0:22–0:33 — What Retirement Conductor is

**Screen:** pitch slide 3.

**Say:**

> Retirement Conductor is the workflow around that deletion. It finds the
> consumers in DataHub, changes only what it is allowed to change, runs the
> consumer's real tests, checks the graph again, and then deletes the old
> column—or stops.

## 0:33–1:22 — One real consumer migration

### 0:33–0:53 — DataHub context becomes an exact change

**Screen:** the fresh Codex task. Show the user's exact prompt, a compact run of
DataHub and Retirement Conductor MCP calls, the exact dbt model, and the plan
digest. Keep long tool bodies collapsed.

**Say:**

> Here is one real campaign. Codex is the operator interface, not the safety
> authority. I ask it to move this consumer from `legacy_status` to
> `order_status`. Through DataHub and our MCP server, it identifies the exact
> dbt model and proposes a one-file change.

### 0:53–1:04 — Human authorization remains external

**Screen:** `HUMAN_AUTHORIZATION_REQUIRED`, the exact file and plan digest,
then the generated authorization command running in a normal terminal.

**Say:**

> Before changing code, it stops. I review the file, validators, and digest,
> then authorize that exact plan in a separate terminal. The agent cannot
> approve itself.

### 1:04–1:22 — Reviewable change and native proof

**Screen:** GitHub **Files changed** with the single-line replacement, followed
by the successful `semantic-dbt` job. Cut back to the same Codex task showing
validation and verified DataHub publication/read-back.

**Say:**

> The same task applies the authorized change. The pull request changes one
> line. dbt parse, build, test, and semantic checks pass. Retirement Conductor
> rechecks DataHub, publishes the campaign result, and reads it back for the
> next operator or agent.

## 1:22–2:32 — The database action and the changed answer

### 1:22–1:47 — Clean path: the old column is really removed

**Screen:** the captured consequential run: the external `producer retire`
command and the filtered clean evidence. Keep only the committed action,
post-action schema, replacement workload, and replay refusal visible.

**Say:**

> Migrating the consumer is not the finish line. In a separate consequential
> run of the same protocol, a privileged command checks DataHub, native
> validation, approval, and the producer schema again. It executes one real
> PostgreSQL `DROP COLUMN`. The old field is gone, the replacement remains, the
> replacement Spark workload still succeeds, and replay is refused.

### 1:47–2:08 — A consumer appears after approval

**Screen:** the late Spark field consumer in DataHub, followed by the fresh
campaign decision changing to `UNSAFE`.

**Say:**

> Now change one fact. After approval, an ad hoc Spark job appears in DataHub
> still reading `legacy_status`. Retirement Conductor checks again at execution
> time. The answer flips to unsafe. The final command commits nothing, and the
> old column stays.

### 2:08–2:32 — The refusal prevents a demonstrated failure

**Screen:** place the late-run result beside the static-signoff control. Show
zero destructive statements and the preserved column on the left; show the
committed drop, failed Spark workload, and SQLSTATE `42703` on the right.

**Say:**

> That is not dashboard theatre. In the matched static-signoff control, nobody
> rechecks the graph. The column is dropped, and the same Spark workload fails
> with SQLSTATE four-two-seven-zero-three: column does not exist. Retirement
> Conductor prevents that exact failure.

## 2:32–2:57 — Workbench and close

**Screen:** Workbench Overview, then one fast click into Evidence. End on the
broken Spark branch and the `UNSAFE` decision.

**Say:**

> The Workbench is the readable view of that consequential campaign: the
> consumers, exact change, native tests, evidence freshness, and why the
> decision changed.
> DataHub is not decoration, and the model does not decide safety. Retirement
> Conductor turns changing context into a verified database change—or a safe
> refusal.

## Final frame

Hold the Workbench for two seconds with the project name and public repository
legible. Do not add a feature list, architecture recap, or spoken thank-you.
