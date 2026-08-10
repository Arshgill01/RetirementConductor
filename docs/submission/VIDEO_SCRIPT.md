# Three-minute video script

Target duration: **2:52–2:57**. Do not fill the remaining seconds with more
features. Leave room for cuts and one natural pause.

The video is an edited proof, not an uninterrupted terminal recording. Every
shown result must come from a real inspected run, but setup, container startup,
indexing waits, and validator runtime should be cut.

## 0:00–0:22 — Three-slide opening

### 0:00–0:07 — The problem

**Screen:** pitch slide 1.

**Say:**

> Here is the problem: changing one warehouse column can break systems your
> repository cannot even see.

### 0:07–0:14 — Why DataHub

**Screen:** pitch slide 2.

**Say:**

> In our test, repository search found one consumer. DataHub found thirty-one,
> across seven pages. So DataHub is not a lookup here. It changes whether the
> column can be removed.

### 0:14–0:22 — The promise

**Screen:** pitch slide 3.

**Say:**

> Retirement Conductor takes it from there: move the consumers we can change,
> run their real tests, check the graph again, and then drop the old field—or
> stop.

## 0:22–1:18 — The agent changes a real consumer

### 0:22–0:43 — DataHub to exact plan

**Screen:** the retained real Codex task, or a fresh task only if the disposable
demo environment has already been prepared. Show the prompt, named MCP calls,
exact file, and plan digest. Keep tool details collapsed unless the tool name
itself is the proof.

**Say:**

> Here is the actual agent run. I ask Codex to replace `legacy_status` with
> `order_status`. It uses DataHub and our MCP server, finds the exact dbt model,
> and produces a one-file plan.

### 0:43–0:55 — Human authority

**Screen:** the agent's `HUMAN_AUTHORIZATION_REQUIRED` result, then the exact
one-file diff. Briefly show the separate terminal where the digest-bound
authorization is recorded.

**Say:**

> And then it stops. That matters: the agent cannot approve its own change. I
> authorize that exact plan in a separate operator terminal.

### 0:55–1:18 — Native proof

**Screen:** the public GitHub pull request: one file changed, semantic-dbt CI
green. Cut to the Codex result showing native validation and verified DataHub
publication read-back.

**Say:**

> That opens a real pull request. dbt parse, build, test, and semantic checks all
> pass. The result is written back to DataHub, read back, and tied to the same
> campaign.

## 1:18–2:32 — Consequential action and reversal

### 1:18–1:43 — Clean path

**Screen:** the captured CP-05 clean run. Show the privileged
`producer retire` command, followed by only these facts:

- `destructive_statements_committed: 1`
- `legacy_column_present: false`
- `replacement_column_preserved: true`
- replacement Spark workload `SUCCEEDED`
- replay `REFUSED`

**Say:**

> Now for the part I cared about: does it actually do anything? In the clean
> run, a separately privileged command checks everything again and really drops
> the PostgreSQL column. One drop. The replacement survives, the Spark workload
> stays healthy, and replay is refused.

### 1:43–2:09 — Late consumer

**Screen:** show a new Spark field consumer appearing, then the Codex
reconciliation result changing to `UNSAFE`.

**Say:**

> Then we make it harder. After approval, a new Spark consumer appears in
> DataHub, still reading `legacy_status`. The answer flips to unsafe.

### 2:09–2:32 — Refusal with a real consequence

**Screen:** the CP-05 late result beside the static control. Keep only:

- Retirement Conductor: `REFUSED_BEFORE_ACTION`, zero destructive statements,
  legacy column still present;
- static sign-off: one drop, Spark `LEGACY_COLUMN_MISSING`, SQLSTATE `42703`.

**Say:**

> The same final command now commits nothing, and the old column stays. This is
> not a staged red badge: in the static-signoff control, the drop goes through
> and Spark actually fails with SQLSTATE four-two-seven-zero-three.

## 2:32–2:57 — Workbench and close

**Screen:** the Workbench overview, then one fast click into Evidence. End on
the broken Spark branch and the `UNSAFE` decision.

**Say:**

> The Workbench is simply the readable view of that same campaign: what changed,
> what passed, what is fresh, and exactly why we stopped. We do not pretend
> DataHub sees the universe. We make the evidence explicit—and when it changes,
> the database change does not happen.

## Final frame

Leave the Workbench visible for two seconds with the project name and public
repository legible. Do not add a spoken feature list, architecture recap, or
“thank you.”
