# Realistic alternative ablation v2 report

## Result

**Classification:** `NO_MATERIAL_ADVANTAGE`

**Recommendation:** `SIMPLIFY`

In the frozen executable foundation matrix, a competent fresh pre-action CI
check matched Retirement Conductor on every predeclared safety, stale-authority,
replay, interruption-recovery, outcome-resolution, and causal-audit property.
It did so with one pre-action workflow and immutable run report instead of a
campaign database plus Retirement Lease and gate ledger. The comparison does
not support retaining that extra producer-action machinery on protocol value
alone.

This is not yet the final native result. CP-03 was assigned no live ports and
the coordination plan explicitly permits protocol fakes for the foundation
action and workload. The classification is therefore fixture/executable-local
evidence. CP-05 must apply the same frozen rule to the CP-01 PostgreSQL action,
CP-02 Superset refresh, and CP-04 downstream outcome probe. A different live
result is valid; changing this corpus or its thresholds after observing that
result is not.

## Frozen boundary

- Assigned base: `b8a839acd0b411d905fa0ed142838cd76ab618f4`
- Frozen protocol: `fixtures/realistic-alternative-ablation-v2/FROZEN.json`
- Frozen digest: `sha256:1f8a357a3ba57ecaaa3ee01049633122337df3b9d50e61a1357907d6c066b577`
- Independent oracle digest: `sha256:c6bffbbb3cac81d38a0a51fbb86b087a240d057477a0062a29790a84ad1dcba8`
- Common action-contract digest: `sha256:07c470e874776cd34ca249e331cfc68ddd80d7b555f615f24c35fb599434fc39`
- Runtime: CPython 3.13.14; Retirement Conductor 0.2.0
- Evidence mode: `fixture executable local`

The oracle imports only Python standard-library modules. It does not import
Retirement Conductor policy, the gate, any comparison arm, or the scenario
runner. It derives observable safety, action, column, workload, approval, and
outcome facts from frozen scenario inputs and checks the separately frozen
expected properties.

## Fair baseline capability

The fresh-CI arm is not a deliberately weak foil. It performs complete paged
DataHub inventory immediately before action; enforces freshness, permissions,
and ambiguity refusal; compares exact membership; rereads the producer
fingerprint; binds current Git/dbt and Superset native validation; checks
approval scope and expiry; calls the same action boundary; resolves uncertain
outcomes by native reread; supports automatic safe retry; and writes a causal
report. It is stateless beyond that report and the common action boundary.

The evaluator rejects the arm if any of those capabilities is disabled. The
baseline is a workflow architecture, not a representation of DataHub or a
named vendor.

## Aggregate observations

| Arm | Unsafe commits | Clean false refusals | Statements attempted / committed | Stale-green reuse | Manual recovery | Audit bindings present |
|---|---:|---:|---:|---:|---:|---:|
| Point-in-time | 8 | 0 | 13 / 13 | 12 | 0 | 76 |
| Fresh CI | 0 | 0 | 4 / 4 | 0 | 0 | 72 |
| Retirement Conductor | 0 | 0 | 4 / 4 | 0 | 0 | 72 |

Audit-binding presence is not a freshness score. The static arm retains its
initial graph/source/approval/validation fields even when they are stale, and
that stale record accompanies eight unsafe commits. Both failure-closed arms
record the current graph, source, approval, validation, action, and outcome
bindings for every persistable result. Both refuse the audit-publication outage
before action, so that scenario intentionally has no reconstructed final
artifact.

The modeled elapsed values are descriptive harness costs only and do not
participate in classification.

## Scenario matrix

| Scenario | Point-in-time | Fresh CI | Retirement Conductor |
|---|---|---|---|
| No drift clean control | permit; one commit | permit; one commit | permit; one commit |
| Late exact-field consumer | unsafe commit | refuse membership drift | refuse reconciliation drift |
| Late table-only/ambiguous edge | unsafe commit | refuse ambiguity | refuse ambiguity |
| DataHub unavailable | unsafe commit | refuse unavailable evidence | refuse unavailable evidence |
| Incomplete pagination | unsafe commit | refuse partial evidence | refuse partial evidence |
| Producer schema drift | unsafe commit | refuse source drift | refuse source drift |
| Git/dbt source or validation drift | unsafe commit | refuse validation drift | refuse validation drift |
| Superset native drift | unsafe commit | refuse native drift | refuse native drift |
| Approval expired or scope changed | unauthorized commit | refuse approval | refuse approval |
| Action replay | one commit; stale sign-off reused | one commit; native state blocks replay | one commit; lease consumption blocks replay |
| Crash before action | automatic retry; one commit | automatic full recheck; one commit | automatic resume; one commit |
| Lost response after action intent | native reread resolves one commit | native reread resolves one commit | native reread resolves one commit |
| Publication/audit artifact unavailable | commits from frozen sign-off | refuse before action | refuse before action |

The publication case separates data safety from required decision
reconstruction. Its source state is otherwise safe, but the failure-closed
contracts require a persistable causal artifact before destructive execution.

## Adversarial evaluator evidence

All five required failure attempts were retained and passed:

1. a missing arm/scenario row refused;
2. a changed frozen input digest refused;
3. one arm using a different native action contract refused;
4. a post-hoc oracle edit refused;
5. a fresh-CI arm with complete paging disabled refused as intentionally biased.

See `artifacts/public/realistic-alternative-ablation-v2/failure-attempts.json`.

## Evidence and retention

- Public index digest: `sha256:48c42ea6d12c2241b9c0405fdca8760dfe96bc5aaee2107ee67a624a7150d1ae`
- Public report digest: `sha256:d5154a22decbd20360c29e5656fa9bf19ea35083c030b8e17c71b9e9d8e0451e`
- Matrix digest: `sha256:5decfb8faa42b7b567c239145b16c77d60d1f60c09c9bcd914bacad6eac3d86c`
- Failure-attempt digest: `sha256:0c622a39ba97401000948412e11c4a169bd50ea9a50cfbaf713d867ac127f1d8`
- Ignored raw run: `.retirement-conductor/cp03-realistic-ablation/raw-run.json`
- Raw run digest: `sha256:d8d51f15522bf2c039777b415122dec425f601c22216e3df3f98f15665657cb4`
- Raw retention: keep through CP-05 integration; do not publish

The public bundle contains aggregate identities, digests, reason codes, and
modeled observations. It contains no credentials, raw rows, private query
results, native service logs, or machine paths.

## Commands observed so far

```text
uv run python scripts/run_realistic_alternative_ablation_v2.py verify-freeze  exit 0
uv run ruff check <CP-03 scripts and test>                               exit 0
uv run ruff format --check <CP-03 scripts and test>                      exit 0
uv run pytest -q tests/unit/test_realistic_alternative_ablation_v2.py    exit 0; 5 passed
uv run python scripts/run_realistic_alternative_ablation_v2.py run       exit 0
uv run python scripts/run_realistic_alternative_ablation_v2.py verify    exit 0
```

The documentation-complete tree is validated again before commit; the exact
repository-wide observations are recorded in the integration note.

## What this proves and does not prove

It proves that the frozen baseline is competent, the evaluator is resistant to
the named comparison failures, the complete 39-row protocol matrix executes,
and the predeclared rule does not award Retirement Conductor an advantage it
did not demonstrate.

It does not prove native PostgreSQL action behavior, live DataHub freshness,
live Superset reconstruction, dbt behavior, downstream breakage prevention,
production coverage, customer value, or that the live CP-05 classification
will remain unchanged.
