# TE-02 — Retirement Gauntlet v2

## Objective

Build a balanced, truth-bearing adversarial corpus that exercises the durable
campaign engine and representative live DataHub/Git/dbt paths. The result must
show both safe progress and safe refusal across substantially different field
replacement semantics. Decorative row volume and direct calls to the pure
policy function do not satisfy this workstream.

## Corpus design

Freeze at least 24 cases across at least three campaign families, for example:

- enum replacement such as `legacy_status` to normalized status;
- same-type but semantically dangerous measures such as gross versus net;
- temporal semantics such as event time versus processing time;
- nullable/defaulted or key-bearing replacements where appropriate.

The final expected outcomes must include at least:

- four `READY_TO_RETIRE` cases;
- six `BLOCKED` cases;
- eight `UNSAFE` cases;
- four `REVIEW_REQUIRED` cases.

Additional cases may use any state, but one negative pattern must not dominate
the suite. Every case declares the controlled consumer set, evidence envelope,
native identities, source versions, planted faults, expected disposition,
decision, refusal/review codes, and causal reason.

## Required difficulty

Across the corpus exercise:

- more than 100 consumers and actual multi-page retrieval;
- multi-hop lineage, duplicate edges, and a harmless graph cycle;
- exact field edges mixed with table-only edges;
- duplicate display names and distinct platform instances;
- removed and deleted/recreated native identities;
- disappearing lineage without a closure receipt;
- delayed indexing, stale evidence, and incomplete permission/paging signals;
- a late consumer after Retirement Lease issue;
- source and owner drift after planning or validation;
- aliases, nested CTEs, macros, generated SQL, ephemeral models, and
  `SELECT *` uncertainty;
- quoted identifiers, comments, and literals containing legacy-field text;
- null inflation, unmapped categories, duplicate keys, aggregate drift,
  freshness drift, and timezone-sensitive behavior;
- malicious metadata or repository text that must remain data;
- replay, interruption, copied state, and stale authorization or lease use.

Use small deterministic fixtures for structure and an ignored medium tier for
scale. Complexity and causality matter more than gigabytes.

## Execution tiers

1. **All cases:** use the real durable campaign store, events, canonical
   manifests, evidence envelopes, receipts, reconciliation, and gate. The
   harness must not call `evaluate_policy` directly to manufacture the
   observed result.
2. **At least twelve cases:** perform live-local DataHub ingestion or metadata
   writes followed by the normal inventory/reconciliation boundary and direct
   aspect inspection where the MCP result is weaker.
3. **At least eight cases:** execute an exact disposable Git/dbt plan, apply or
   refusal, native validation, and receipt path.
4. **At least four sequence cases:** exercise readiness over time, including
   issue, watch, invalidation or consumption, publication/read-back, and gate
   refusal or execution.

The independent oracle must not import product policy or reuse campaign output
to calculate expectations. Intentionally corrupt at least one oracle result and
prove the comparator rejects it.

## Acceptance thresholds

- zero false `READY_TO_RETIRE` outcomes;
- exact expected decision and refusal/review codes for every case;
- 100% expected-consumer recall in controlled graphs;
- no unexpected consumer closure;
- exact target equality for every native apply;
- all ready cases have fresh complete evidence, accepted native receipts,
  verified publication, and equivalent reconciliation;
- every stale lease or plan refuses without another producer action;
- twin generation is byte-reproducible and live reruns are semantically
  equivalent after removing time/run identity;
- per-tier execution counts and limitations are public and inspectable.

## Implementation boundary

Own new paths for `fixtures/retirement-gauntlet-v2/`, the independent oracle,
runner, evidence generator, schemas if strictly needed, and focused tests.
Reuse existing campaign, DataHub, Git/dbt, watch, publication, and gate code.
Fix product defects exposed by the corpus narrowly and record them.

Do not edit semantic-model code, Codex prompts, skill/MCP implementation,
submission pages, shared product documents, shared Makefile, packaging
metadata, or existing Phase 06 artifacts. Put requested shared changes in
`docs/plans/integration-notes-gauntlet-v2.md`.

## Public evidence

Publish one compact index with:

- corpus and oracle digests;
- balanced decision counts;
- execution-tier counts;
- per-case expected/observed decisions and stable codes;
- false-readiness and recall totals;
- live DataHub and native validator versions;
- sequence outcomes and producer-action counts;
- defect/fix observations;
- limitations and evidence classifications.

Raw rows, private paths, credentials, query text, and large source artifacts
remain ignored.

## Task prompt

> Implement TE-02 completely. Read `AGENTS.md` and
> `docs/plans/10-winning-truth-experiments.md`, then follow this brief. Work on
> branch `codex/retirement-gauntlet-v2` in an isolated worktree based on
> `codex/winning-truth-experiments-plan`. Freeze the independent oracle before
> executing product cases, run all required tiers, inspect generated artifacts,
> and continue through `make check`. Respect every frozen-file boundary and
> finish with clean integration notes.
