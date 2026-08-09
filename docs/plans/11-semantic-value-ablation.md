# TE-01 — semantic and DataHub context value ablation

## Objective

Determine whether the optional Gemini semantic planner produces measurable
value beyond deterministic selection, and whether DataHub context changes the
quality of its accepted validation plan. Do not integrate the model into the
canonical CLI or MCP path during this workstream.

## Experimental arms

Run the same frozen scenario corpus through:

1. **Deterministic baseline** — a conservative, documented selector over the
   same safe validation primitive vocabulary.
2. **Gemini dbt-only** — exact repository, manifest, field, and validator
   context without DataHub governance, usage, quality, or lineage context.
3. **Gemini DataHub + dbt** — the complete bounded context currently intended
   for the semantic planner.

Use the same model identifier, generation settings, prompt template, trusted
clock, policy, and proposal kernel for both Gemini arms. Execute at least three
independent model attempts per scenario and arm. Record native response IDs,
token counts, latency, proposal digests, kernel result, and accepted check set.

## Frozen scenario corpus

Create at least twelve semantic cases before the first live call. Include:

- glossary-defined category mapping;
- real-query grouping and aggregate behavior;
- quality assertions defining null or uniqueness expectations;
- a freshness requirement distinguishable from ingestion freshness;
- exact output parity appropriate for one consumer but not another;
- compatible physical types with incompatible business meaning;
- ownership present without validation authority;
- missing glossary, query, or quality context;
- contradictory DataHub and dbt evidence;
- prompt injection in metadata descriptions or query text;
- irrelevant rich context that should not create extra checks;
- an evidence-expiry or source-fingerprint mismatch.

Each case declares available evidence, planted risks, safe primitive set,
minimum sufficient check set, forbidden checks, and expected kernel outcome.
The oracle must not call the model or import the selector under test.

Use synthetic public-safe context unless a live-local DataHub reread is
material to the case. Retain enough live cases to prove that the context shape
matches the actual DataHub boundary. Empty context is evidence of absence only
for that observation, never proof that a field has no consumers.

## Metrics

For every arm report:

- kernel-valid proposal rate;
- safety-critical planted-fault coverage;
- minimum-sufficient-plan match rate;
- forbidden or unsupported check attempt rate;
- unnecessary accepted-check count;
- cross-run check-set stability;
- human-edit distance to the oracle plan;
- latency and input/output token counts;
- context-only cases resolved correctly;
- rejected prompt-injection and foreign-authority attempts.

Also report paired differences between full-context Gemini, dbt-only Gemini,
and the deterministic baseline. Do not average away a safety-critical miss.

## Predeclared decision rule

All arms must preserve deterministic authority: zero accepted foreign identity,
authorization, unsupported evidence, executable SQL, arbitrary target, or
policy override.

Recommend `KEEP` for nested Gemini only if full-context Gemini:

- has no safety-critical regression relative to the deterministic baseline;
- correctly resolves at least two predeclared context-only cases that both the
  deterministic baseline and dbt-only Gemini miss, **or** reduces the mean
  accepted test set by at least 25% with identical planted-fault coverage;
- reaches at least 90% exact safe-plan acceptance across repeated runs; and
- demonstrates a concrete operator or PR artifact improvement, not merely a
  more fluent rationale.

Recommend `REMOVE` from the product and headline if it fails that rule.
`SIMPLIFY` is allowed when only the deterministic PR/CI boundary earns its
place. `INCONCLUSIVE` requires a specific unavailable evidence source and must
not be used merely because results are disappointing.

Separately report whether DataHub context adds value over dbt-only Gemini. A
nested model can fail the product-value threshold even when DataHub context
improves its output.

## Implementation boundary

Owned paths may include:

- new `fixtures/semantic-ablation-v2/` truth inputs;
- a new independent oracle/evaluation module;
- a new live runner and public-evidence generator;
- focused tests;
- narrowly necessary edits to `semantic_model_planner.py` and
  `semantic_validation.py` to support controlled context arms.

Do not change the safe primitive vocabulary after the scenario digest is
frozen unless the initial corpus proves an existing primitive cannot be
represented. Record such a change as a new experiment version rather than
rewriting the old result.

Do not edit the canonical skill, MCP server, CLI, agent evidence, product
documents, shared Makefile, packaging metadata, or existing semantic PR
evidence. Put requested integration hunks in
`docs/plans/integration-notes-semantic-ablation.md`.

## Acceptance

- The corpus is frozen before live outputs and has a published digest.
- All three arms execute against identical scenario identities.
- Repeated model runs are real and explicitly identify provider/model.
- The deterministic kernel rejects every authority-smuggling probe.
- Aggregate and per-scenario results are public-safe and reproducible from
  retained raw evidence.
- Focused tests and `make check` pass.
- The report makes an evidence-backed `KEEP`, `SIMPLIFY`, `REMOVE`, or
  `INCONCLUSIVE` recommendation.

## Task prompt

> Implement TE-01 completely. Read `AGENTS.md` and
> `docs/plans/10-winning-truth-experiments.md`, then follow this brief. Work on
> branch `codex/semantic-value-ablation` in an isolated worktree based on
> `codex/winning-truth-experiments-plan`. Freeze the corpus before live model
> calls, run every arm, inspect the evidence, and continue through `make check`.
> Respect every frozen-file boundary and finish with clean integration notes.
