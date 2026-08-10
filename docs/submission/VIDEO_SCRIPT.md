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

> A database field almost never belongs to one team. Replace it, and a model,
> dashboard, or Spark job you do not own can fail.

### 0:07–0:14 — Why DataHub

**Screen:** pitch slide 2.

**Say:**

> In one live test, repository analysis found one consumer. Complete DataHub
> field lineage found thirty-one. That is why DataHub changes the decision; it
> is not decoration.

### 0:14–0:22 — The promise

**Screen:** pitch slide 3.

**Say:**

> Retirement Conductor turns that graph into one workflow: discover, change,
> test natively, recheck, then remove the old field—or refuse.

## 0:22–1:18 — The agent changes a real consumer

### 0:22–0:43 — DataHub to exact plan

**Screen:** a fresh Codex task. Show the prompt, named MCP calls, exact file,
and plan digest. Keep tool details collapsed unless the tool name itself is the
proof.

**Say:**

> Codex is the operator. A project skill and sixteen-tool MCP server let it
> inspect DataHub and drive the same campaign engine as the CLI. It resolves the
> exact fields, finds one changeable dbt model, and proposes one file change.

### 0:43–0:55 — Human authority

**Screen:** the agent's `HUMAN_AUTHORIZATION_REQUIRED` result, then the exact
one-file diff. Briefly show the separate terminal where the digest-bound
authorization is recorded.

**Say:**

> Then it stops. The agent cannot approve itself. I review and authorize this
> exact digest outside the agent.

### 0:55–1:18 — Native proof

**Screen:** the public GitHub pull request: one file changed, semantic-dbt CI
green. Cut to the Codex result showing native validation and verified DataHub
publication read-back.

**Say:**

> The approved change goes through a real pull request. dbt parse, build, test,
> and semantic validation pass. Retirement Conductor records the native receipt,
> rechecks DataHub, writes the result back, and verifies that another agent can
> read it.

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

> The final command runs outside Codex with separate PostgreSQL credentials. It
> freshly checks DataHub, the native consumers, approval, and the producer
> schema. In the clean run it commits exactly one drop, preserves the replacement,
> the replacement Spark workload stays healthy, and replay is refused.

### 1:43–2:09 — Late consumer

**Screen:** show a new Spark field consumer appearing, then the Codex
reconciliation result changing to `UNSAFE`.

**Say:**

> Now the important case. After the original approval, a Spark job appears in
> DataHub still reading `legacy_status`. The same fresh reconciliation changes
> the answer to unsafe.

### 2:09–2:32 — Refusal with a real consequence

**Screen:** the CP-05 late result beside the static control. Keep only:

- Retirement Conductor: `REFUSED_BEFORE_ACTION`, zero destructive statements,
  legacy column still present;
- static sign-off: one drop, Spark `LEGACY_COLUMN_MISSING`, SQLSTATE `42703`.

**Say:**

> Retirement Conductor performs zero destructive statements and preserves the
> column. This is not a cosmetic warning: in the matched static-signoff control,
> the drop goes through and Spark fails with SQLSTATE four-two-seven-zero-three.

## 2:32–2:57 — Workbench and close

**Screen:** the Workbench overview, then one fast click into Evidence. End on
the broken Spark branch and the `UNSAFE` decision.

**Say:**

> The Workbench reads that same campaign store: the exact cause, consumers,
> change, validation, freshness, and event history. It is deliberately not a
> privileged database console. Retirement Conductor does not promise it found
> the universe. It makes the evidence explicit, changes what it can prove, and
> blocks the database change when that evidence changes.

## Final frame

Leave the Workbench visible for two seconds with the project name and public
repository legible. Do not add a spoken feature list, architecture recap, or
“thank you.”
