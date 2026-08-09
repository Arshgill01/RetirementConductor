# TE-04 — evidence-driven integration and definitive unified run

**Audited integration base:** `codex/truth-experiments-integrated`

## Launch gate

Do not launch this task until TE-01, TE-02, and TE-03 have completed with
clean worktrees, public-safe reports, canonical digests, and explicit
recommendations. This task owns shared product changes and resolves conflicts.

The integration owner completed the first audit and merged the three accepted
histories into the audited base above. Read
`docs/plans/15-truth-experiment-integration-audit.md` before making changes.
Spot-check its calculations and preserve each original evidence digest; do not
repeat paid model calls merely to recreate already accepted evidence.

## Objective

Select the simplest architecture justified by the three ablations, integrate
the winning evidence, and record one fresh Codex run that demonstrates the
complete product without prescribing its exact tool order or expected final
decision.

## Phase 1 — inspect before merging

The first integration audit completed the checks below. TE-04 must spot-check
them against the merged histories and stop if the integrated evidence differs:

1. inspect commits and diffs;
2. rerun focused acceptance;
3. verify raw/public evidence bindings;
4. check the frozen corpus preceded observed output;
5. verify failures were retained;
6. reproduce aggregate metrics;
7. compare the recommendation with the predeclared threshold.

Reject or repair a workstream that changes expectations after observation,
compares different inputs across arms, imports the tested implementation into
its oracle, hides failed runs, or claims live evidence from fixtures.

## Phase 2 — architecture decisions

Record explicit decisions for:

- nested Gemini planner: `KEEP`, `SIMPLIFY`, or `REMOVE`;
- project skill: `KEEP`, `SIMPLIFY`, or `REMOVE`;
- Retirement Conductor MCP as primary Codex boundary: `KEEP`, `SIMPLIFY`, or
  `REMOVE`;
- Gauntlet scenarios promoted into normal or release acceptance.

If Gemini loses, remove it from the headline and canonical run. Preserve the
deterministic semantic PR/CI boundary when that boundary independently adds
value. Remove dead model-only code if it has no supported experimental or
product role.

If Gemini wins, expose the smallest advisory operation needed by Codex. Do not
turn every internal step into another MCP tool, and do not let nested model
output authorize, generate arbitrary executable content, validate, or decide
readiness.

If the skill has no measurable marginal benefit, shorten it to the instructions
that do. If the MCP has no measurable operational benefit, investigate the
cause rather than adding tools by default.

## Definitive run requirements

Record one new minimally prompted Codex task over fresh disposable state:

1. The user names one legacy field, one intended replacement, and the desired
   outcome. The prompt does not name exact tool calls, order, blocker codes, or
   expected decision.
2. Codex explicitly records its model, version, reasoning setting, sandbox,
   approvals, enabled MCP servers, available tools, and skill status.
3. DataHub MCP is enabled. Unrelated plugins and mutation capabilities are
   absent from the dedicated acceptance environment.
4. Codex resolves exact fields and inspects schema, lineage, ownership,
   glossary, quality, query, and freshness context when available.
5. The campaign inventories through its cache-bypassed authoritative boundary
   and explains differences from direct MCP observations.
6. The selected semantic strategy produces an exact reviewed migration and
   validation plan.
7. Codex stops for durable human authorization. The operator performs only the
   exact external authorization command.
8. Codex applies and natively validates the exact Git/dbt target.
9. The artifact is pushed to a disposable public GitHub PR; the exact head and
   named passing CI check are reread and bound.
10. Fresh reconciliation publishes one DataHub campaign summary and verifies
    agent-visible read-back. A fresh agent search demonstrates that later
    agents can inherit the result.
11. The campaign becomes ready only if canonical policy permits it, then
    issues an inspected short-lived Retirement Lease. Use a harmless sentinel,
    never warehouse deletion.
12. A new consumer is added through supported DataHub ingestion or metadata
    APIs after lease issue.
13. Codex uses `reconcile_retirement_lease_now`, recognizes the changed graph,
    and explains the decision reversal.
14. The preserved old lease refuses and no second producer action occurs.

Use as few user interventions as the durable authorization boundary permits.
Resume one Codex task rather than staging a sequence of unrelated agents.

## Evidence acceptance

The public bundle must record:

- exact prompts, model/host configuration, tool inventory, and skill status;
- invariant results and observed tool order;
- zero unexpected shell or unrelated MCP calls in the chosen boundary;
- DataHub, MCP, dbt, GitHub, package, and Codex versions;
- source, plan, approval, apply, validation, PR, CI, reconciliation,
  publication, lease, watch, gate, and producer-action bindings;
- before/after graph and campaign decisions;
- public PR URL and exact check URL;
- inherited DataHub document read-back;
- raw trace digests and public redaction classification;
- limitations, including author/operator and disposable-local boundaries.

Acceptance asserts product invariants, not a hard-coded exact tool order.
`make check`, installed-agent handshake, focused Gauntlet acceptance, site
tests, and link/public/secret checks must pass on the integrated tree.

## Phase 3 — handoff to cleanup and submission

After the run passes, produce a compact cleanup inventory ordered by judge
impact:

1. dead or losing experimental code;
2. responsibility-heavy modules with safe extraction boundaries;
3. duplicate runners and artifact generators;
4. historical documentation that should move out of the judge path;
5. README, Evidence & Trust Center, video, Devpost, GitHub metadata, and
   release updates.

Do not perform unrelated aesthetic refactors while debugging the definitive
run. The resulting architecture and evidence become the refactor baseline.

## Task prompt

> TE-01, TE-02, and TE-03 are complete. Implement TE-04 from a new isolated
> worktree and branch `codex/definitive-unified-run` based on
> `codex/truth-experiments-integrated`. Read `AGENTS.md`,
> `docs/plans/10-winning-truth-experiments.md`, this brief, all three public
> reports, their integration notes, and
> `docs/plans/15-truth-experiment-integration-audit.md`. Spot-check the merged
> evidence, then implement its decisions: remove nested Gemini, keep bounded
> DataHub context, keep the project skill and product MCP, and make no
> capability-bounded claim. Execute the definitive minimally prompted live run
> with a real public PR/CI binding and late-consumer lease reversal. Continue
> until every acceptance and repository check passes.
