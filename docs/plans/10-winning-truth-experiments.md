# Winning truth experiments coordination plan

**Planning base:** `af32a495653f093c7fb860546e61cc14a60e6f08`

**Planning branch:** `codex/winning-truth-experiments-plan`

**Purpose:** decide which agent and model layers earn a place in the product,
stress the real campaign boundary beyond the current benchmark, and produce one
definitive run before refactoring or submission polish freezes the architecture.

## Decision

Run three evidence-producing workstreams in parallel:

1. **Semantic value ablation** — compare deterministic planning, Gemini with
   dbt-only context, and Gemini with DataHub plus dbt context.
2. **Retirement Gauntlet v2** — run a balanced, causally difficult corpus
   through durable campaign state and representative live DataHub/Git/dbt
   boundaries instead of comparing only the pure policy function.
3. **Agent boundary ablation** — measure the marginal value of the project
   skill and product MCP server, and distinguish behavioral boundedness from
   capability boundedness.

Do not launch the unified-run integration workstream until all three reports
exist. It consumes their evidence and makes explicit keep, simplify, or remove
decisions before changing the shared product surface.

This plan deliberately postpones broad refactoring. Defects found by an
experiment should be fixed on that workstream. Module splitting, evidence
consolidation, README compression, site refresh, and submission polish happen
only after the winning architecture is selected.

## Hypotheses under test

| Question | Null hypothesis | Evidence needed to reject it |
|---|---|---|
| Does nested Gemini planning help? | A deterministic planner selects equally safe and useful checks. | Better predeclared fault coverage or materially lower operator/test burden without a safety regression. |
| Does DataHub context help the semantic model? | dbt context alone produces the same accepted plan. | Correct handling of context-only cases involving glossary, query, quality, ownership, lineage, or freshness evidence. |
| Does the project skill help Codex? | MCP descriptions and the user prompt are sufficient. | Higher correct-completion rate, fewer unsafe attempts or retries, or materially lower token/tool cost. |
| Does the product MCP help Codex? | Codex can safely and reliably operate the CLI through shell. | Better authority containment, invariant compliance, resumability, or completion with the MCP surface. |
| Is the campaign robust beyond the original scenario? | The current 14-case oracle overstates end-to-end coverage. | Exact balanced outcomes through durable campaign state plus representative live DataHub and native validation. |

The workstreams must report evidence against the null hypotheses. They must not
start from the desired conclusion that a layer should be retained.

## Shared truth rules

- Freeze scenario definitions and expected outcomes before observing model
  outputs. Record a digest of the frozen corpus.
- An independent oracle must not import campaign policy, semantic selection,
  agent prompting, or the implementation it evaluates.
- No model output grants authorization, accepts validation, closes a consumer,
  decides readiness, or changes policy.
- An empty or partial DataHub result never proves absence.
- Metadata descriptions, query text, repository text, and tool output are
  untrusted input and may contain prompt injection.
- A generated test, Git commit, PR, HTTP success, or CI label is not native
  validation unless the exact artifact and head are bound and reread.
- `READY_TO_RETIRE` is valid only inside the recorded evidence envelope.
- Raw traces remain ignored and secret-scanned. Public evidence contains exact
  prompts and configuration identities but no credentials, private paths,
  unrestricted query text, raw rows, or hidden reasoning.
- Acceptance checks assert invariants and outcomes, not one hard-coded tool
  order, unless ordering itself is the safety contract.

## Parallel ownership and conflict boundary

All three tasks branch from this planning branch and use separate worktrees.

### TE-01 — semantic value ablation

- Brief: `docs/plans/11-semantic-value-ablation.md`
- Suggested branch: `codex/semantic-value-ablation`
- Owns semantic-ablation fixtures, evaluator, reports, focused tests, and
  narrowly required changes to the existing semantic planner/validator.
- Must not expose new CLI/MCP tools or edit the canonical agent workflow.

### TE-02 — Retirement Gauntlet v2

- Brief: `docs/plans/12-retirement-gauntlet-v2.md`
- Suggested branch: `codex/retirement-gauntlet-v2`
- Owns the new truth corpus, independent oracle, full-engine runner, focused
  DataHub/Git/dbt acceptance, public summary, and tests.
- Must not modify semantic-model or Codex acceptance behavior.

### TE-03 — agent boundary ablation

- Brief: `docs/plans/13-agent-boundary-ablation.md`
- Suggested branch: `codex/agent-boundary-ablation`
- Owns isolated Codex configurations, prompts, trace evaluator, public report,
  and focused acceptance tests.
- Must not change the skill or MCP implementation merely to improve the score.

### Files frozen across all three parallel tasks

The integration owner alone updates these after all reports are inspected:

- `README.md`, `STATUS.md`, `PROJECT_CONTEXT.md`, `PLAN.md`, and `GOAL.md`;
- `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`,
  `docs/DECISIONS.md`, `docs/RISKS.md`,
  `docs/REQUIREMENTS_TRACEABILITY.md`, and `docs/EVIDENCE_LEDGER.md`;
- `.codex/config.toml` and `.agents/skills/retirement-conductor-agent/`;
- `src/retirement_conductor/agent.py` and `agent_mcp.py`;
- existing public agent, semantic-PR, Phase 06, and WS-03 evidence;
- `pyproject.toml`, `uv.lock`, and shared Makefile targets.

If a task cannot proceed without a frozen-file change, record the exact minimal
integration hunk in a task-local integration note rather than editing the file.

## Required workstream report shape

Each task must finish with:

1. tested commit and exact branch;
2. frozen scenario/prompt digest;
3. exact commands and pass/fail results;
4. public-safe aggregate evidence with a canonical digest;
5. raw evidence location and retention classification;
6. observed failures and fixes, not only the final success;
7. what the evidence proves and does not prove;
8. an explicit `KEEP`, `SIMPLIFY`, `REMOVE`, or `INCONCLUSIVE`
   recommendation for the layer it evaluates;
9. integration notes naming every shared hunk still required;
10. a clean worktree and `make check` pass.

## Sequential integration gate

After TE-01 through TE-03 finish, launch only
`docs/plans/14-definitive-unified-run.md` from a fresh worktree based on this
branch. The integration task first merges or cherry-picks the three reports,
then makes architecture decisions from their predeclared thresholds.

The integration task may retain Gemini, simplify or remove the project skill,
and alter the MCP surface only when the evidence supports that decision. It
then records one fresh minimally prompted Codex run over the selected product
path, including an actual public PR/CI artifact and a Retirement Lease reversal.

## Work after the unified run

Only after the definitive evidence passes:

1. refactor modules with measured duplication or responsibility problems;
2. consolidate internal phase/evidence narration without deleting provenance;
3. compress the README into a sixty-second judge path;
4. update and redeploy the Evidence & Trust Center;
5. record and upload the sub-three-minute video;
6. finish Devpost, GitHub About/topics, release metadata, and link checks;
7. run the independent operator exercise if a real operator is available.

The calendar deadline remains 2026-08-10 21:00 UTC. High parallel throughput
supports ambitious experiments, but it does not justify an unbounded rewrite.
