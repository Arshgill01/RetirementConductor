# Consequential foundation integration audit

Handoff status: integrated and exercised by CP-05 on commit `e9d7d97`. CP-01
is behind durable gate intent, CP-02 contributes independent final gate-time
evidence, CP-04 is independent consequence evidence, and the CP-03 frozen
corpus/oracle/thresholds/classifications remain unchanged.

**Planning base:** `b8a839acd0b411d905fa0ed142838cd76ab618f4`

**Integrated behavior head:** `155a1e0`

**Integration branch:** `codex/consequential-foundations-integrated`

## Verdict

CP-01 through CP-04 are accepted as foundations for CP-05. Their lineages,
frozen-file boundaries, public evidence digests, focused verifiers, and
combined repository behavior were independently inspected.

Do not interpret acceptance as a positive final product verdict. CP-03 froze a
competent alternative and classified the fixture-level comparison
`NO_MATERIAL_ADVANTAGE`. That result is a hostile null hypothesis for CP-05.
It is not yet authority to remove the Retirement Lease because CP-03 was
explicitly protocol-local and did not execute the CP-01, CP-02, or CP-04 live
boundaries.

CP-05 must preserve the frozen CP-03 corpus and decision rule, run the native
comparison, and accept `SIMPLIFY` or `REFRAME` if equality remains.

## Integrated commits

| Foundation | Source commit(s) | Integrated commit(s) | Recommendation |
|---|---|---|---|
| CP-01 PostgreSQL producer action | `f7f5776`, `ea10476` | `d1720b1`, `836431a` | `KEEP` |
| CP-02 Superset gate refresh | `199c9aa` | `847a4b8` | `KEEP` |
| CP-03 realistic alternative | `a33f05c` | `94dceed` | `SIMPLIFY`; fixture classification `NO_MATERIAL_ADVANTAGE` |
| CP-04 native breakage lab | `5f4e6d6` | `155a1e0` | `KEEP_SPARK` |

All four source branches have merge base `b8a839a`. No cherry-pick conflict
occurred. Shared frozen files were unchanged by the foundation branches.

## Independently verified evidence

- CP-01 index digest:
  `sha256:54d3432968bb37f99abcf006893470b2b39664e244be17cb561f2e0673947af8`.
- CP-02 index digest:
  `sha256:09f68d7603412f0afe6bfb3404b75e84ae1b1080aca4b17d2558483a4fbcd171`.
- CP-03 index digest:
  `sha256:48c42ea6d12c2241b9c0405fdca8760dfe96bc5aaee2107ee67a624a7150d1ae`.
- CP-04 index digest:
  `sha256:9ffd98967d4388d6c547f31e627fbc2b2d5336041e0d29e208c681c1a93e7238`.

Each self-digest was recomputed from canonical sorted JSON after removing its
digest field and matched byte-for-byte. CP-03's freeze and public verifier and
CP-04's public verifier also passed independently.

## Foundation facts CP-05 may rely on

### CP-01

- One quoted, allowlisted `postgres_drop_column_v1` boundary exists.
- It uses separate observer and mutation clients and rechecks schema,
  dependency, identity, and permission facts under an `ACCESS EXCLUSIVE` lock.
- It never emits `CASCADE` or accepts arbitrary SQL.
- Native reread distinguishes `COMMITTED`, `NOT_COMMITTED`, and
  `OUTCOME_UNKNOWN`; an unknown result cannot be blindly retried.
- The module has no campaign authority and persists no gate intent. CP-05 must
  claim the existing one-use producer plan before invoking it.
- Three committed statements in CP-01 evidence came from separate acceptance
  cases, not three executions of one plan.

### CP-02

- `SupersetGateVerifier` exposes only authenticated reads and forced chart
  execution; its protocol has no update method.
- The live gate-verifier principal was separately credentialed and an attempted
  dataset update was refused.
- The verifier binds dataset, chart, database, accepted plan/receipt,
  post-apply source fingerprint, server/adapter versions, and semantic result.
- It returns a fresh evidence source. It never decides policy.
- DataHub graph inventory remains mandatory and complementary; the official
  connector's table-level lineage cannot become a native field fact.

### CP-03

- Static sign-off committed eight unsafe actions in 13 frozen scenarios.
- The modeled fresh-CI and Retirement Conductor arms both had zero unsafe
  commits and zero clean-control false refusals.
- The baseline includes complete paging, freshness, exact membership, source
  and validation rereads, approval checks, native outcome resolution, and a
  causal immutable run report. Removing any of these to make it lose violates
  the frozen fairness contract.
- CP-03 used protocol-local action and workload boundaries. CP-05 must run the
  identical live action and observation topology before changing product
  architecture.

### CP-04

- Pinned Spark 3.5.3 and PostgreSQL JDBC 42.7.4 executed over 128 deterministic
  rows in two independently reconstructed environments.
- Dropping `legacy_status` caused normalized `LEGACY_COLUMN_MISSING`, SQLSTATE
  `42703`, and exit 42, while the replacement workload retained its digest.
- The denied-action control executed no statement and both workloads remained
  healthy.
- The consumer descriptor is not DataHub lineage. CP-05 must ingest and
  directly reread a corresponding DataHub aspect.
- CP-05 must use CP-01 for the destructive action. CP-04's lab-native direct
  drop exists only to establish the outcome oracle.

## CP-05 non-negotiable integration rules

1. Do not simplify or remove the lease before running the frozen native
   comparison; that would destroy the arm being evaluated.
2. Give fresh CI the same action-time DataHub, Git/dbt, Superset, approval,
   producer-schema, action, and workload observations as Retirement Conductor.
3. Record action intent durably before giving CP-01 the mutation client.
4. Keep PostgreSQL mutation credentials out of Codex, the skill, MCP, and the
   general campaign process.
5. Invoke CP-02 inside final gate verification, merge its normalized evidence,
   and let deterministic policy decide. Verifier success alone grants nothing.
6. Ingest and reread CP-04's real consumer identity through DataHub; do not
   promote its descriptor directly into graph evidence.
7. Use clean, independently reconstructed native environments for each arm.
8. Preserve CP-03's scenarios, capability list, oracle, thresholds, and result
   labels unchanged.
9. Classify an ambiguous PostgreSQL result from native state before any retry;
   otherwise retain consumed `OUTCOME_UNKNOWN` authority.
10. Publish per-arm facts even if the result is unfavorable.

## Combined validation

On the conflict-free integrated tree:

```text
make check
Result: 317 passed, 1 intentionally opt-in live PostgreSQL test skipped;
Ruff passed; formatting passed; strict mypy passed over 106 source files;
repository validation passed for 204 required files, 101 Markdown files, and
178 relative links; secret scan passed for 481 text files; public-artifact
review passed for 109 files; source and wheel builds passed; diff check passed.
```

Focused independent verification also passed:

- CP-01: 19 unit tests; live evidence retained from its completed 16-case run.
- CP-02: 27 unit tests and the retained 21-case live matrix.
- CP-03: frozen protocol, public result, and 5 evaluator tests.
- CP-04: public verifier and 5 evidence tests.

The integration worktree is the correct base for CP-05. The original Workbench
worktree and its untracked reassessment file were not modified.
