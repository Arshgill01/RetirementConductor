# TE-01 semantic value ablation completion report

## Outcome

TE-01 is complete on branch `codex/semantic-value-ablation`. The tested
behavior and public-evidence commit is `86b1524`, based on planning commit
`f521a4d` from `codex/winning-truth-experiments-plan`. The corpus freeze is
commit `4c171ce`.

The predeclared product recommendation is **REMOVE** nested Gemini from the
product and headline. Full DataHub plus dbt context improved safety-critical
planted-fault coverage, but the model did not meet the minimum-sufficient-plan,
operator-artifact, or 90% exact-plan thresholds.

DataHub context separately **ADDS_VALUE** over dbt-only context: it increased
safety-critical planted-fault coverage from 53.3% to 100.0%. That context value
did not make the nested model product-worthy because exact plan match remained
20.0%, 48 unnecessary checks were accepted, and the mean operator edit
distance remained worse than the deterministic baseline.

## Frozen truth and execution identity

- Experiment: `TE-01-semantic-value-ablation-v2`
- Scenario count: 15
- Attempts: 135 final attempts, three per scenario and arm
- Corpus file digest:
  `sha256:76620aac13eba687633d367a47c7865ca605d3e1da32c56c547f7ea9e4d27654`
- Corpus semantic digest:
  `sha256:bbc8b2135219e13edc55b8f07fd405c05edf4c51f4ea565780333781374eb992`
- Independent truth digest:
  `sha256:4f8120f3fd3280f278ec421ddd782b0b30745e64535c261ff8b70b8bdaa5af89`
- Freeze record digest:
  `sha256:682aaa00a53f941068a45bbbfa54a04818887684ac13decb9c9ad3786cd3a2c6`
- Provider and resolved model: Google Vertex AI,
  `gemini-3-flash-preview`
- Generation: temperature 0, one candidate, 4096 maximum output tokens
- Native model responses: 180 unique response IDs across 90 live attempts
- Canonical public summary:
  `sha256:14e4c48066fcc62bd50c2d35a26642a3f6f91c59cae5ac371c7215eac5f6c359`

The independent oracle imports only Python standard-library modules and reads
the frozen truth file. It does not import campaign policy, semantic selection,
model prompting, or the proposal kernel under evaluation.

Two scenarios bind their context shape to retained public evidence from the
previous live-local DataHub semantic run. The remaining scenarios are
synthetic and public-safe. No empty observation is interpreted as proof of
global absence.

## Aggregate observations

| Arm | Exact plan | Critical fault coverage | Forbidden or unsupported | Stability | Mean edits |
|---|---:|---:|---:|---:|---:|
| Deterministic | 60.0% | 53.3% | 0.0% | 100.0% | 0.867 |
| Gemini dbt-only | 20.0% | 53.3% | 6.7% | 100.0% | 1.733 |
| Gemini DataHub + dbt | 20.0% | 100.0% | 0.0% | 86.7% | 1.111 |

The full-context model selected every required safety detector but consistently
overselected. It produced no exclusive context-only exact-plan win because the
extra checks prevented minimum-sufficient matches. One irrelevant-rich-context
attempt was refused by the deterministic kernel, which accounts for the 97.8%
expected-outcome match in that arm.

All six deterministic authority-smuggling probes refused: foreign identity,
authorization, unsupported evidence, executable SQL, arbitrary target, and
policy override. The prompt-injection scenario produced no accepted foreign
authority in any arm.

## Commands and results

| Command | Result |
|---|---|
| `uv run python scripts/run_semantic_value_ablation.py freeze` | PASS; 15 scenarios frozen before live calls |
| `uv run python scripts/run_semantic_value_ablation.py verify-freeze` | PASS |
| `make test-winning-workstreams` | PASS; 55 tests before live execution |
| `SEMANTIC_MODEL_PROJECT=<configured-project> SEMANTIC_MODEL_ALLOW_LIVE=true uv run python scripts/run_semantic_value_ablation.py run` | PASS; final 135-attempt matrix complete |
| `SEMANTIC_MODEL_PROJECT=<configured-project> SEMANTIC_MODEL_ALLOW_LIVE=true uv run python scripts/run_semantic_value_ablation.py publish` | PASS |
| `SEMANTIC_MODEL_PROJECT=<configured-project> SEMANTIC_MODEL_ALLOW_LIVE=true uv run python scripts/run_semantic_value_ablation.py verify` | PASS; canonical summary verified |
| `uv run pytest -q tests/unit/test_semantic_ablation.py tests/unit/test_semantic_model_planner.py tests/unit/test_semantic_validation.py` | PASS; 18 tests |
| `make check` | PASS at `86b1524`; Ruff, format, strict mypy over 91 files, 251 tests, repository validation, secret and public-artifact scans, source and wheel builds, and `git diff --check` |

The configured project is represented only by its digest in public evidence;
the project value and application identity are not published.

## Public and raw evidence

Public-safe artifacts are in
`artifacts/public/semantic-ablation-v2/`. `summary.json` is the canonical
aggregate; `results.json` retains per-attempt response IDs, token counts,
latency, proposal digests, kernel results, and accepted check sets;
`review-artifact.json` records concrete operator edits; `configuration.json`
contains exact prompts and safe configuration identity; and
`observed-failures.json` preserves the defects and repairs.

Raw requests and responses remain ignored private evidence at
`.retirement-conductor/semantic-ablation-v2/raw`. The preliminary 45-attempt
full-context run affected by the evidence-kind harness defect remains at
`.retirement-conductor/semantic-ablation-v2/observed-defects/`. Raw evidence is
retained locally through integration inspection and must never be packaged or
published.

## Observed failures and fixes

1. Before any live call, the deterministic selector read “no not-null test” as
   a positive signal. The match was narrowed and regression-tested without
   changing frozen truth.
2. Sequential live execution was interrupted after five completed attempts and
   resumed with four independent workers. Prompts, model settings, policy,
   trusted clock, corpus, and scoring did not change.
3. The first full-context projection used an evidence kind outside the existing
   semantic-plan schema. All preliminary traces were preserved; the runner was
   corrected to an existing DataHub evidence kind, a real-schema regression
   test was added, and all 45 full-context attempts were rerun. The preliminary
   invalid summary digest was
   `sha256:d66708919330d5f79c47938b54c79f12cc6aef834ddee0acc1055d39fd2d1a8c`.
4. One protocol-refused attempt initially omitted the resolved model from its
   public projection. The value was recovered from the retained native
   `modelVersion` without another model call and regression-tested.

## What this proves and does not prove

This experiment proves the relative plan-selection behavior of the three arms
for the frozen corpus, prompt, provider/model, policy, and evidence shapes. It
also proves that the deterministic kernel rejected every predeclared authority
probe and that DataHub context exposed safety-relevant checks the dbt-only arm
missed.

It does not prove production safety, hidden-consumer absence, native validation
success, behavior for another model or prompt, customer value, or that the
current deterministic selector is sufficient. Its 53.3% critical-fault
coverage is direct evidence that a replacement deterministic selector must use
the useful bounded DataHub signals rather than discard them.

The exact shared follow-up is recorded in
[integration-notes-semantic-ablation.md](integration-notes-semantic-ablation.md).
