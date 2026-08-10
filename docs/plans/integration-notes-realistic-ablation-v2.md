# CP-03 integration notes — realistic alternative ablation v2

## Foundation handoff

- Exact base: `b8a839acd0b411d905fa0ed142838cd76ab618f4`
- Branch: `codex/cp-03-realistic-alternative-ablation-v2`
- Foundation classification: `NO_MATERIAL_ADVANTAGE`
- Recommendation: `SIMPLIFY`
- Frozen digest: `sha256:1f8a357a3ba57ecaaa3ee01049633122337df3b9d50e61a1357907d6c066b577`
- Oracle digest: `sha256:c6bffbbb3cac81d38a0a51fbb86b087a240d057477a0062a29790a84ad1dcba8`
- Public index digest: `sha256:48c42ea6d12c2241b9c0405fdca8760dfe96bc5aaee2107ee67a624a7150d1ae`
- Raw run: ignored `.retirement-conductor/cp03-realistic-ablation/raw-run.json`
- Services: none started; CP-03 owns no live ports by coordination contract

## Frozen-file compliance

CP-03 did not edit `README.md`, `GOAL.md`, `STATUS.md`, `PLAN.md`,
`PROJECT_CONTEXT.md`, canonical product/architecture/contracts/decision/risk/
traceability/evidence documents, shared gate/CLI/agent/MCP source, the skill,
Codex configuration, schemas, dependencies, lockfiles, existing public
evidence, or existing Make targets.

All implementation is task-local:

- `fixtures/realistic-alternative-ablation-v2/FROZEN.json`
- `scripts/realistic_alternative_ablation_oracle.py`
- `scripts/realistic_alternative_ablation.py`
- `scripts/run_realistic_alternative_ablation_v2.py`
- `tests/unit/test_realistic_alternative_ablation_v2.py`
- `artifacts/public/realistic-alternative-ablation-v2/`
- this note and the task report

## Required CP-05 native substitutions

Do not edit the frozen corpus, expected properties, baseline capability list,
or classification thresholds. Add a CP-05 live runner or injected adapter
layer that preserves each frozen scenario input digest and records the actual
native observation beside it.

1. **CP-01 action:** replace `NativeAction` only at the port boundary with the
   exact CP-01 allowlisted PostgreSQL plan/apply/observe workflow. Require
   schema/table/column equality, action-digest equality, `CASCADE=false`, one
   maximum commit, and native resolution of the lost-response case. If the
   CP-01 contract is not observationally equivalent, classify the live run
   `INCONCLUSIVE`; do not alter this fixture.
2. **DataHub:** feed complete cache-bypassed paged inventory, permission,
   freshness, ambiguity, and exact membership observations to both fresh-CI
   and Retirement Conductor from the same captured action-time boundary. A
   shared capture may be normalized twice, but neither arm may receive a
   broader or newer graph.
3. **Git/dbt:** bind the same source commit/fingerprint and native validation
   receipt to both arms and inject the same drift after approval. Fresh CI must
   reread it; do not leave the stale result as an intentional baseline gap.
4. **CP-02 Superset:** replace the frozen boolean with the CP-02 read-only
   gate-time observation. Both failure-closed arms must receive the same
   dataset/chart/database identity, source fingerprint, forced execution,
   semantic digest, permission, version, and outage result.
5. **Approval:** issue one approval scope and expiry for both arms. Fresh CI
   must validate exact membership, native binding, scope, and trusted time.
   Retirement Conductor may additionally bind the durable campaign/lease.
6. **CP-04 outcome:** replace `downstream_workload_healthy` with the native
   CP-04 workload probe before and after the common action. Keep its consumer
   descriptor distinct from DataHub lineage until CP-05 ingests and rereads
   that lineage.
7. **Publication failure:** fail the fresh-CI artifact sink and Retirement
   Conductor publication/readback at the same stage. Record action safety
   separately from audit reconstructability.

The decisive CP-05 native minimum is clean control, late exact-field consumer,
replay, and lost response. The remaining scenarios should run when their CP-01
and CP-02 boundaries are available; any omitted required comparable scenario
forces `INCONCLUSIVE` under the frozen rule.

## Smallest shared integration hunks

Only CP-05 may make these shared changes:

- wire the CP-01 action behind `src/retirement_conductor/gate.py` after the
  existing exact lease/campaign verification;
- wire the CP-02 normalized native observation into the same gate-time source
  verification without letting it decide policy;
- expose the CP-04 native workload result only as outcome evidence, not as
  authorization;
- add a unique live CP-05 runner/target and a separate public live bundle;
- update canonical claims, decisions, risks, traceability, status, and evidence
  ledger to the live classification, including `SIMPLIFY` or `REFRAME` if it
  remains `NO_MATERIAL_ADVANTAGE`.

No CP-03 hunk requires changes to product policy or the current gate merely to
make the Retirement Conductor arm win.

## Classification consequence

If the live results preserve the foundation equality, the predeclared result
remains `NO_MATERIAL_ADVANTAGE`. The integration should `SIMPLIFY` the
producer-action path toward the competent fresh-check design or explicitly
`REFRAME` the durable campaign as coordination/audit infrastructure whose value
is not superior pre-action safety. It must not retain lease/gate complexity on
the earlier static-signoff comparison alone.

If Retirement Conductor prevents a native unsafe/replayed action that the fair
fresh-CI arm permits without a clean regression, use `MATERIALLY_BETTER`. If
safety is equal but native interruption recovery or causal audit is strictly
better, use `SAFETY_EQUIVALENT_PROTOCOL_ADVANTAGE`. If the native comparison
cannot remain identical, use `INCONCLUSIVE`, never a positive recommendation.

## Validation and completion record

Observed on CPython 3.13.14:

- frozen protocol verification: 13 scenarios, digest matched;
- focused CP-03 suite: 5 passed;
- public evidence verifier: `NO_MATERIAL_ADVANTAGE`, `SIMPLIFY`, index digest
  matched;
- adversarial evaluator probes: 5 of 5 refused as frozen;
- Ruff: all checks passed; 145 files formatted;
- strict mypy: no issues in 98 source files;
- pytest: 266 passed;
- repository validation: 204 required files, 94 Markdown files, 175 relative
  links;
- secret scan: 445 text files passed;
- public-artifact review: 96 files passed;
- source distribution and wheel: built successfully;
- `git diff --check`: passed.

No service cleanup is required because CP-03 started no Docker Compose project
or live port. The clean commit identifier is reported in the task handoff after
the commit exists; it cannot be embedded in the commit that creates it.
