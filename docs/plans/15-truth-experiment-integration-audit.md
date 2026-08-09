# Truth experiment integration audit

**Integration branch:** `codex/truth-experiments-integrated`

**Planning base:** `f521a4d`

**Audited workstreams:**

- TE-01 `codex/semantic-value-ablation` at `fd31c28`;
- TE-02 `codex/retirement-gauntlet-v2` at `0447e06`;
- TE-03 `codex/agent-boundary-ablation` at `4d68383`.

## Audit verdict

All three workstreams are accepted for sequential integration. Their frozen
inputs preceded observed output, public artifacts verify against their
recorded digests, focused tests pass, and their recommendations follow the
predeclared thresholds. Acceptance is bounded by the limitations below; it is
not permission to turn controlled evidence into a production-safety claim.

## Evidence-driven architecture decisions

1. **Remove nested Gemini from the supported product and headline.** TE-01
   reproduced 135 final attempts, including 90 live Gemini attempts and 180
   unique native response identifiers. Full DataHub context improved critical
   fault coverage from 53.3% to 100%, but exact minimum-plan accuracy remained
   20%, stability fell to 86.7%, and the model added 48 unnecessary accepted
   checks. It failed the predeclared product-value rule.
2. **Keep bounded DataHub semantic context.** The failed conclusion concerns
   nested model selection, not DataHub context. Deterministic planning or
   operator review should retain safety-relevant glossary, query, quality,
   lineage, ownership, and freshness signals where their evidence envelope is
   complete and current.
3. **Keep the project skill.** In TE-03 it improved correct completion from
   66.67% to 95.83%, reduced median calls from 15.5 to 10, reduced median
   retries from 8.5 to 4, and eliminated three observed unsafe model attempts
   for this exact Codex host and model.
4. **Keep the Retirement Conductor MCP as the primary Codex product surface.**
   MCP-only completion was 66.67% versus 29.17% through CLI/shell, with lower
   call and retry burden. Deterministic campaign controls, not MCP or model
   compliance, still own authorization and safety.
5. **Keep the durable campaign, reconciliation, and Retirement Lease
   boundary.** TE-02 matched all 24 independent-oracle cases, recalled 121 of
   121 controlled consumers, produced no false readiness, and refused stale,
   reversed, expired, and replayed producer plans.
6. **Do not claim capability boundedness.** Every TE-03 condition exposed
   shell and file editing, while DataHub MCP advertised metadata mutation
   tools. TE-04 must restrict the dedicated host where possible and publish
   the exact remaining capability surface.

## Reproduction performed by the integration owner

- TE-01 frozen corpus and canonical public summary verified; 18 focused tests
  passed. Independent inspection confirmed 45 attempts per arm, three attempts
  per scenario, and 180 unique response identifiers across 90 live attempts.
- TE-02 frozen corpus and oracle verified; 30 focused store and gauntlet tests
  passed. Independent inspection confirmed 24 matched cases, the declared
  decision distribution, 15 DataHub cases, eight native Git/dbt cases, four
  lease sequences, 121 controlled consumers, and one producer action.
- TE-03 eight focused tests passed. Reaggregating the retained 72 formal runs
  reproduced every prompt, run, score, recommendation, and failure. The
  aggregate command regenerated only `generated_at`, `tested_commit`, and the
  resulting self-digest; the committed public artifact was restored unchanged
  after inspection.
- All three public self-digests independently verified with the canonical
  digest implementation.

## Limitations and required TE-04 repairs

### TE-01 verification ergonomics

Public verification currently requires the live-call opt-in environment flag
even though verification performs no model call. This does not invalidate the
evidence, but the final acceptance surface should separate offline verification
from paid or networked execution.

### TE-02 non-applicability evidence

The gauntlet creates its non-applicability receipts from controlled fixture
truth. The receipts are exact and digest-bound, but the digest does not prove
who produced the evidence and their `evidence_ids` are not independently read
back from a native source. Do not expose `record_non_applicability` as a model
authority path or claim independent validation from it. The definitive run
must close its real Git/dbt consumer through native validation and treat every
new or opaque DataHub consumer as unsafe.

The canonical gauntlet command is module execution:
`uv run python -m scripts.run_retirement_gauntlet_v2`. Direct file execution
does not resolve the repository's `scripts` package and is not the supported
entry point.

### TE-03 aggregate provenance

TE-03's aggregate is substantively reproducible but not byte-idempotent because
it records the current timestamp and commit before calculating its public
self-digest. The definitive evidence generator should either provide an
offline verify mode or separate an immutable result digest from mutable
generation provenance.

### Scope of all three experiments

The experiments establish behavior for frozen controlled corpora, live-local
services, and the exact recorded model/host configurations. They do not prove
production graph coverage, customer adoption, universal model behavior, or the
absence of unknown consumers.

## TE-04 launch gate

Launch TE-04 from this integrated branch in a new isolated worktree. Its first
commit should record the final architecture decisions in shared controlling
documents. Its product run must then use the retained skill and product MCP,
exclude nested Gemini, restrict unrelated capabilities, execute one real
public PR/CI-bound Git/dbt migration, publish and reread DataHub state, issue a
short-lived lease, add a genuinely new consumer, reverse readiness, and refuse
the stale lease without a second producer action.
