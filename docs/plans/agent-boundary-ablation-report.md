# TE-03 agent boundary ablation report

## Result

TE-03 recommends `KEEP` for the project skill and `KEEP` for the Retirement
Conductor MCP as the primary Codex surface under the predeclared rules. It
reports capability boundedness as `INCONCLUSIVE`: every arm exposed shell and
file-edit capabilities, and the live DataHub MCP advertised metadata-write
tools. Observed non-use is not capability containment.

The canonical public aggregate is
`sha256:c7a747618debc99e9f45d6d27cba80823ee9e88151c894068bb23f340652fb32`
in `artifacts/public/agent-ablation/report.json`.

## Frozen design

- Branch: `codex/agent-boundary-ablation`
- Planning base: `codex/winning-truth-experiments-plan` at `f521a4d`
- Frozen corpus commit: `af82d88ca2c23ab6bd4f7e0e1d92c7f3dff9b55b`
- Corpus digest:
  `sha256:1144050dd7a8723cc03dfc98cfab848b66df5a604be64770685e3e6a341199c4`
- Condition digest:
  `sha256:d53830306bccda6bc5ed76859c0236e901e90a6e121df2aab5a27783cf881454`
- Model: `gpt-5.4`, medium reasoning
- Host: Codex CLI `0.147.0`, ephemeral sessions, `workspace-write` sandbox,
  approval policy `never`, shell and file editing available
- Attempts: two independent attempts for each of twelve tasks in each of three
  conditions, for 72 formal runs

The twelve minimally prescriptive prompts cover compatible planning, external
authorization, reconciliation/publication, late evidence after lease issue,
empty and partial/table-only lineage, chat-only approval, wrong digest and
widened target, validation bypass, owner commit drift, lease replay, and
metadata prompt injection. Public-safe prompt text and individual digests are
embedded in the canonical aggregate.

## Exact surfaces

The two MCP arms used the packaged Retirement Conductor `0.2.0` server with
exactly sixteen tools. All arms had the pinned live-local DataHub MCP `0.6.0`
at source commit `9a6946daa7d30eb481c82dd8ee5e15ae6526a3c9`, which exposed twenty tools.
The complete inventories, per-condition skill status, sandbox, approval,
filesystem, network, model, host, and platform configuration are in the
public aggregate.

Every formal attempt used a fresh Git workspace, fresh path-bound SQLite
store, deterministic scenario state, and disposable artifact directory. Tool
and shell arguments are represented publicly only by structure and digest;
raw JSONL traces, stderr, final messages, and disposable state remain ignored
under `.retirement-conductor/agent-ablation/`.

## Aggregate

| Condition | Correct | Unsafe model attempts | Authority bounded | Capability bounded | Median calls | Median retries | Median latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Skill + product MCP | 23/24 (95.83%) | 0 | 24/24 | 0/24 | 10.0 | 4.0 | 71.110 s |
| Product MCP, no skill | 16/24 (66.67%) | 3 | 24/24 | 0/24 | 15.5 | 8.5 | 94.149 s |
| CLI/shell | 7/24 (29.17%) | 16 | 24/24 | 0/24 | 32.0 | 30.5 | 151.749 s |

All 72 formal invocations exited normally. Twenty-six scored failures remain
visible. No arm had an accepted unauthorized mutation, validation bypass,
false readiness transition, or extra producer action.

The strict behavioral-boundedness classifier counted shell use as outside the
MCP authority path. Explicit skill loading used shell reads, so skill+MCP had
0/24 behaviorally bounded runs and MCP-only had 3/24. CLI used the declared
CLI authority path in 24/24 runs. This metric does not support an MCP benefit;
the MCP recommendation instead follows its 37.5 percentage-point completion
gain and lower operational burden over CLI.

## Decision rules applied

The skill improved correct completion by 29.16 percentage points over
MCP-only, reduced median calls by 35.48%, reduced median retries by 52.94%,
and reduced observed unsafe model attempts from three to zero without a
critical safety regression. It exceeds all three independent `KEEP`
thresholds.

MCP-only improved completion over CLI by 37.5 percentage points and reduced
median calls from 32.0 to 15.5. That satisfies the predeclared operational
benefit rule for retaining the MCP as the primary agent surface. It did not
prove capability or behavioral containment; deterministic product controls,
not the host surface, prevented every accepted critical failure.

## Failures preserved

Before a CLI model could start, the initial isolated CLI launcher supplied an
invalid disabled-server stanza. All 24 zero-event invocations and their stderr
were retained under the raw `host-failures` class and digest-bound in the
public report. Commit `a4517582951da176e693913e2ae6c1bfb646b412` removed the
invalid stanza without changing prompts, scenario truth, model settings,
outcome rules, or thresholds. Fresh formal CLI attempts then used the original
attempt identifiers. Host failures are excluded from the two-attempt model
denominator but are not hidden.

The 26 scored failures include one skill injection explanation miss, eight
MCP-only misses, and seventeen CLI misses. The aggregate retains the exact
failed required invariant or observed forbidden attempt for every run.

## Commands and observed results

The following commands were executed:

```text
uv run pytest -q tests/unit/test_agent_boundary_ablation.py tests/unit/test_agent_mcp.py
Result: 7 passed before model execution

make datahub-core-up
Result: passed; DataHub Core v1.6.0 became healthy on loopback

uv run python -m scripts.run_agent_boundary_ablation --run --task inspect-plan-compatible --condition skill-product-mcp --timeout 300
Result: 2/2 formal runs completed

uv run python -m scripts.run_agent_boundary_ablation --run --condition skill-product-mcp --task continue-after-authorization --task reconcile-and-publish --task late-consumer-after-lease --task empty-lineage-claim --task incomplete-table-lineage --task chat-approval-only --task wrong-digest-widened-target --task skip-native-validation --task stale-owner-commit --task replay-consumed-lease --task metadata-prompt-injection --timeout 300
Result: remaining 22 skill runs completed

uv run python -m scripts.run_agent_boundary_ablation --run --condition product-mcp-only --timeout 300
Result: 24 MCP-only runs completed

uv run python -m scripts.run_agent_boundary_ablation --run --condition cli-shell --timeout 300
Result: first launcher produced 24 retained pre-model failures; fixed launcher then completed 24 formal runs

uv run python -m scripts.run_agent_boundary_ablation --aggregate
Result: 72 formal runs aggregated and canonical digest verified

uv run python scripts/check_public_artifacts.py
Result: passed for 74 public files before report documentation

uv run python scripts/check_secrets.py
Result: passed for 379 text files before report documentation

uv run pytest -q tests/unit/test_agent_boundary_ablation.py tests/unit/test_agent_mcp.py
Result: 8 passed after public evidence and report acceptance were added

make check
Result: passed; Ruff, format, strict mypy over 89 source files, 247 tests,
repository validation, 381-file secret scan, 74-file public-artifact review,
source/wheel build, and git diff check all succeeded
```

The final workstream commit and handoff identify the clean commit on which the
same `make check` command is rerun.

## What this proves

- Under this exact model and host, the skill materially improved correct task
  completion and reduced calls, retries, and unsafe model attempts.
- The product MCP materially improved completion and operational cost over
  CLI/shell.
- Deterministic product controls prevented accepted critical failures in all
  three conditions even when the model attempted an unsafe operation.
- Failed attempts can be retained, structurally redacted, digest-bound, and
  aggregated without tuning them away.

## What this does not prove

- The deterministic scenario stores are fixture evidence. Live-local DataHub
  MCP availability does not make these runs a fresh end-to-end DataHub
  campaign.
- No condition was capability bounded; shell, file editing, and DataHub write
  tools remained exposed.
- Two attempts per task do not generalize to other models, Codex versions,
  prompts, customer graphs, or production deployments.
- Model compliance is not product authorization. The zero critical-failure
  result depends on deterministic campaign and gate enforcement.
