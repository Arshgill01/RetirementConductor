# TE-01 semantic ablation integration notes

## Integration decision

Use tested evidence commit `86b1524` from branch
`codex/semantic-value-ablation`. The predeclared decision is **REMOVE** nested
Gemini from the supported product and headline. Do not describe this as proof
that DataHub context lacks value: the full-context arm improved
safety-critical planted-fault coverage by 46.7 percentage points over dbt-only
Gemini. The failed layer is remote nested-model plan selection under the
minimum-sufficient and operator-value rules.

The integration owner should prefer a deterministic, context-aware selector or
an explicit operator review of bounded DataHub signals. TE-01 does not itself
authorize a new selector design. Any replacement needs a new frozen experiment
rather than reinterpretation of these results.

## Shared frozen-file hunks

The TE-01 worktree intentionally did not edit these files. Apply the following
minimal changes only during sequential integration after TE-02 and TE-03 are
also inspected.

### Product and headline

- `README.md`: remove the optional Vertex/Gemini semantic planner from the
  sixty-second product path and supported-feature claims. Link TE-01 as the
  reason the layer was removed rather than hiding the negative result.
- `docs/PRODUCT.md`: remove the paragraph presenting the optional Vertex AI
  semantic planner as an advisory product layer. Retain the deterministic
  principle that models cannot authorize, accept validation, or decide
  readiness.
- `PROJECT_CONTEXT.md`, `PLAN.md`, and `GOAL.md`: remove any future-work or
  completion language that treats nested Gemini as part of the selected
  architecture. Do not alter the core DataHub/Git/dbt campaign objective.
- `STATUS.md`: add TE-01 tested commit `86b1524`, summary digest
  `sha256:14e4c48066fcc62bd50c2d35a26642a3f6f91c59cae5ac371c7215eac5f6c359`,
  and `REMOVE` recommendation. State separately that DataHub context improved
  fault coverage but did not satisfy product-value thresholds.

### Architecture, decisions, risks, and traceability

- `docs/ARCHITECTURE.md`: remove the live semantic-model tool loop from the
  selected architecture. Keep deterministic proposal validation and
  template-bound test materialization only if integration evidence still uses
  them without a nested model.
- `docs/DECISIONS.md`: add a new decision that supersedes D-045 for supported
  architecture. Preserve D-045 and the old live PR evidence as historical
  provenance; do not rewrite them as if the experiment never existed.
- `docs/RISKS.md`: update R-41 from “contained for optional semantic planner”
  to the selected no-live-model boundary. Retain the authority-smuggling probes
  for any future proposal source. Add the observed over-selection/operator-load
  risk: full context covered faults but added 48 unnecessary accepted checks.
- `docs/REQUIREMENTS_TRACEABILITY.md`: link TE-01 only to requirements whose
  deterministic authority or semantic-validation boundary it exercised. Do not
  present plan selection as native validation.
- `docs/EVIDENCE_LEDGER.md`: add a TE-01 entry with branch, tested commit,
  freeze/truth/summary digests, exact provider/model, 135 final attempts, raw
  classification, observed defects, `REMOVE` recommendation, DataHub context
  finding, and non-claims.

### Code and packaging boundary

- `src/retirement_conductor/semantic_model_planner.py`: remove the Vertex
  transport, live environment settings, prompt/tool loop, and model-specific
  evidence surface from the supported package after integration confirms no
  selected path imports them.
- `src/retirement_conductor/semantic_validation.py`: retain the new
  incompatible-replacement precondition and the deterministic safe-primitive,
  template, digest, and approval kernel if used by the simplified PR/CI
  boundary. Model-independent safety behavior should not be deleted merely
  because Gemini is removed.
- `pyproject.toml`, `uv.lock`, and package-release checks: no dependency hunk is
  needed for TE-01 because the implementation uses the standard library. If
  the live planner is removed, verify no model-specific package file remains in
  the wheel allowlist or release inventory.
- `Makefile`: update `test-winning-workstreams` only if the integrated product
  removes model-specific tests. Keep semantic kernel and TE-01 evidence tests
  runnable as historical regression coverage where practical.
- `.codex/config.toml`, `.agents/skills/retirement-conductor-agent/`,
  `src/retirement_conductor/agent.py`, and
  `src/retirement_conductor/agent_mcp.py`: TE-01 requires no direct hunk. Any
  change there must come from TE-03 or the unified integration decision.

### Existing evidence

- Do not edit the files under `artifacts/public/semantic-pr/`; they are valid
  historical evidence for the earlier bounded live PR experiment.
- Keep `artifacts/public/semantic-ablation-v2/` byte-identical to tested commit
  `86b1524` when integrating. Its canonical summary digest must remain stable.
- Never commit or publish `.retirement-conductor/semantic-ablation-v2/` raw or
  observed-defect traces.

## Suggested integration sequence

1. Cherry-pick `4c171ce` and `86b1524` or merge the complete TE-01 branch.
2. Verify the frozen corpus and public digest before changing shared narration.
3. Inspect TE-02 and TE-03 recommendations.
4. Make the selected-architecture decision in one new decision record.
5. Remove the live planner only after its imports, packaging inventory, tests,
   and historical evidence links are mapped.
6. Run the definitive unified experiment from the selected architecture.
7. Run `make check` and inspect package contents and public-artifact scans.

No CLI, MCP, agent workflow, packaging metadata, shared Makefile target, or
canonical product/evidence document was changed by TE-01.
