# TE-02 integration notes — Retirement Gauntlet v2

## Workstream identity

- Branch: `codex/retirement-gauntlet-v2`
- Planning base: `codex/winning-truth-experiments-plan` at `f521a4d`
- Frozen truth commit: `f10a7e3`
- Frozen corpus SHA-256:
  `b0e9c23f0d206e4a8925da578ce6e4fdf315a47b057198b2cc1c4e1fcf9ff03c`
- Frozen oracle SHA-256:
  `ff67034d1b4b6eff85c80dcb94f499dd8e293a5f353f39fbb1ea2ec2a9facdb0`

The oracle was committed before any product campaign case was executed. The
runner verifies the frozen byte digests and has no code path that rewrites the
truth files.

## Shared hunks intentionally deferred

The coordination plan freezes every file below. Integration should apply only
these minimal follow-ups after inspecting the TE-01 through TE-03 reports:

1. `README.md`: link the compact Gauntlet v2 index and state its fixture/live
   evidence boundary.
2. `STATUS.md` and `docs/EVIDENCE_LEDGER.md`: record the tested workstream
   commit, exact commands, public evidence digest, modes, and limitations.
3. `docs/ARCHITECTURE.md` and `docs/CONTRACTS.md`: document
   `REVIEW_REQUIREMENT_RECORDED` and `NON_APPLICABILITY_RECORDED`. A review
   event grants no authority; a non-applicability event accepts only one exact,
   digest-bound consumer/evidence binding.
4. `docs/DECISIONS.md`: record why durable review requirements and explicit
   non-applicability receipts were retained after the gauntlet exposed the two
   unreachable/unevidenced paths.
5. `docs/RISKS.md`: update synthetic circularity and disappearing-lineage risks
   from the corruption and non-applicability probes.
6. `docs/REQUIREMENTS_TRACEABILITY.md`: attach the Gauntlet v2 evidence to
   RC-002, RC-003, RC-005, RC-008 through RC-012, RC-016, RC-019, and RC-020.
7. `Makefile`: add a shared `retirement-gauntlet-v2` target that runs
   `make git-dbt-tool` followed by
   `uv run python -m scripts.run_retirement_gauntlet_v2`.

No semantic-model code, Codex behavior, skill/MCP implementation, packaging
metadata, existing Phase 06 evidence, or submission surface was changed.

## Integration recommendation

`KEEP` the durable campaign/gate boundary. The experiment is intended to test
whether it holds across balanced semantics and hostile sequences, not to add a
second policy engine. Retain the two narrow event types only if the final
evidence has zero false readiness, exact code parity, and no closure without an
evidence receipt. Otherwise mark this recommendation `INCONCLUSIVE` and do not
promote the event changes.

## Evidence classification and retention

- Frozen corpus and oracle: committed deterministic fixture truth.
- DataHub tier: live-local Core and MCP over controlled fixture metadata.
- Git/dbt tier: live-local disposable repositories and dbt validation.
- Raw command/aspect/receipt state: ignored under
  `.retirement-conductor/gauntlet-v2/`; operator-managed retention.
- Public aggregate: `artifacts/public/retirement-gauntlet-v2/index.json`.
- Production and customer-value claims: explicitly not established.

Final tested commit, observed failures/fixes, command results, public digest,
and remaining limitations are appended only after the full run, artifact
inspection, `make check`, and clean-worktree verification succeed.
