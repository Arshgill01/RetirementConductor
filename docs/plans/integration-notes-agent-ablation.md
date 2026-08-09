# Agent ablation integration notes

## Recommendation

- Project skill: `KEEP`.
- Retirement Conductor MCP as the primary Codex surface: `KEEP`.
- Capability boundedness: `INCONCLUSIVE`; do not claim it from observed
  non-use.

The skill crossed every predeclared keep threshold: +29.16 percentage points
correct completion, 35.48% fewer median calls, 52.94% fewer median retries,
and zero rather than three unsafe model attempts, with no critical safety
regression. MCP-only beat CLI by 37.5 percentage points and halved median
calls, which is sufficient operational benefit even though the strict
behavioral classifier did not favor MCP.

## Shared hunks for the integration owner

No product, skill, MCP, schema, package, or shared Makefile change is required
to realize the evidence-backed choice. Do not tune
`.agents/skills/retirement-conductor-agent/`,
`src/retirement_conductor/agent.py`, or
`src/retirement_conductor/agent_mcp.py` from this experiment.

After inspecting and reproducing the report, the integration owner should make
only these shared documentation updates:

1. Add one decision-log entry recording `KEEP` for the skill and product MCP,
   and `INCONCLUSIVE` for capability boundedness, with the canonical report
   digest.
2. Add the TE-03 branch, freeze commit, execution commits, 72-run aggregate,
   raw-retention class, and limitations to `docs/EVIDENCE_LEDGER.md`.
3. Update `STATUS.md` and the unified-run plan only after TE-01 and TE-02 are
   also inspected; do not promote fixture task truth to a live product claim.

## Definitive-run constraints

The unified run should use the skill and product MCP, but it must not inherit a
capability-bounded claim. Its dedicated host should remove shell and unrelated
mutation surfaces if the host supports that configuration. The pinned DataHub
MCP advertised these mutation-capable tools during TE-03:
`add_owners`, `add_structured_properties`, `add_tags`, `add_terms`,
`remove_domains`, `remove_owners`, `remove_structured_properties`,
`remove_tags`, `remove_terms`, `save_document`, `set_domains`, and
`update_description`. Either restrict them or record their exposure plainly.

The definitive run should also avoid memorizing the skill's exact call order.
Retain outcome-based scoring and the separate distinctions among:

- behaviorally bounded tool selection;
- deterministic authority containment;
- host-level capability containment.

## Integration commands

```text
git cherry-pick af82d88ca2c23ab6bd4f7e0e1d92c7f3dff9b55b
git cherry-pick a4517582951da176e693913e2ae6c1bfb646b412
Then cherry-pick the final TE-03 evidence commit reported by the workstream handoff.
uv run pytest -q tests/unit/test_agent_boundary_ablation.py
uv run python scripts/check_public_artifacts.py
uv run python scripts/check_secrets.py
make check
```

The first two commits preserve the pre-run freeze and the retained host-failure
repair separately. The final evidence commit contains the public aggregate,
report, focused acceptance, and this integration note.
