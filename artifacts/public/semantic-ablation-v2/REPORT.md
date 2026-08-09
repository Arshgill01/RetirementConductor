# TE-01 semantic value ablation report

Canonical summary: `sha256:14e4c48066fcc62bd50c2d35a26642a3f6f91c59cae5ac371c7215eac5f6c359`.

## Result

Nested Gemini recommendation: **REMOVE**. DataHub context finding: **ADDS_VALUE**.

| Arm | Exact plan | Fault coverage | Forbidden/unsupported | Stability | Mean edits |
|---|---:|---:|---:|---:|---:|
| Deterministic | 60.0% | 53.3% | 0.0% | 100.0% | 0.867 |
| Gemini dbt-only | 20.0% | 53.3% | 6.7% | 100.0% | 1.733 |
| Gemini DataHub + dbt | 20.0% | 100.0% | 0.0% | 86.7% | 1.111 |

## Predeclared decision rule

- no safety regression: PASS
- two exclusive context only wins or 25 percent reduction: FAIL
- at least 90 percent exact safe plan acceptance: FAIL
- concrete operator review artifact improvement: FAIL

Full context improved safety-critical planted-fault coverage over the dbt-only arm, but exact minimum-sufficient-plan accuracy remained 20.0% and the operator review artifact required more edits than the deterministic baseline. The context signal has value; the nested model layer does not earn product inclusion under the frozen rule.

## Evidence boundary

The 15 scenarios are synthetic except for two shapes bound to retained live-local public DataHub evidence. This is model-selection evidence, not native-validation, production, customer, or hidden-consumer evidence.
Raw model requests and responses remain ignored private evidence under `.retirement-conductor/semantic-ablation-v2/`.
