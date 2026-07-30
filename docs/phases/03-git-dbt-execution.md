# Phase 03 — Git and dbt execution

## Outcome

One exact repository consumer discovered through the campaign is changed on a
reviewable branch, protected against concurrent edits and unauthorized scope,
validated through dbt, and represented by a live native receipt.

## Dependencies

- phase 02 live DataHub inventory;
- disposable Git repository containing a real dbt project;
- local or isolated warehouse target safe for dbt execution.

## Scope

In scope:

- repository identity and commit pinning;
- layered repository discovery using text, dbt manifest, and compiled state;
- exact allowlisted file mutation;
- branch creation and reviewable diff;
- replacement existence and compatibility preflight;
- dbt parse, build, and tests;
- optional bounded data comparison when configured;
- rollback through Git;
- native receipt and adverse cases.

Excluded:

- merging to a production branch;
- automatic broad repository refactors;
- support for every templating language;
- claiming non-default branches were searched unless explicitly configured;
- treating a clean text search as complete repository evidence.

## Deliverables

- Git/dbt adapter implementing the native lifecycle;
- repository evidence source in the coverage envelope;
- consumer-to-file identity mapping;
- frozen plan with exact files and replacement tokens;
- content and commit preconditions;
- plan-only and apply capability separation;
- validator runner with safe redaction;
- rollback verification;
- live Git/dbt receipt;
- fixture suite for aliases, macros, generated SQL, `SELECT *`, and scope
  violations.

## Work breakdown

1. Record repository URL or safe identity, default branch, and exact commit.
2. Run text discovery for high recall.
3. parse dbt manifest and compiled artifacts for structural evidence.
4. Classify direct, indirect, generated, and uncertain references.
5. Map only one authorized consumer to exact files for the first live apply.
6. Verify the replacement field against live schema and dbt source metadata.
7. Produce and display a minimal plan and diff.
8. Bind approval to commit, plan digest, file set, and replacement identity.
9. Create a branch and reread commit plus file hashes.
10. Refuse branch movement, changed content, unexpected files, or ambiguous
    patch tokens.
11. Apply atomically within the repository boundary.
12. Run dbt parse, build, and project tests in the disposable target.
13. Compare actual diff and modified file set with the approved plan.
14. Exercise Git rollback and verify original content and tests.
15. Reapply once to prove idempotent behavior.
16. Emit the live native receipt and attach it to the campaign.

## Acceptance evidence

Required behavior:

- repository discovery finds the real local consumer and declares its blind
  spots;
- non-default branch coverage is explicit;
- source commit and file fingerprints are recorded;
- plan-only credentials or mode cannot write;
- stale commit or file content refuses before mutation;
- an unauthorized file or expanded target set refuses;
- missing or incompatible replacement refuses;
- actual diff changes only approved content;
- dbt parse, build, and required tests pass;
- a semantically wrong replacement fixture fails validation or requires
  review;
- rollback restores content and passes verification;
- repeated apply creates no duplicate change;
- live receipt maps to exactly one campaign consumer.

Required commands:

```bash
make check
retirement-conductor adapter git-dbt preflight --campaign <id>
retirement-conductor adapter git-dbt plan --campaign <id>
retirement-conductor adapter git-dbt apply --campaign <id>
retirement-conductor adapter git-dbt validate --campaign <id>
retirement-conductor campaign evaluate --campaign <id>
git diff --check
```

Inspect:

- discovery layers and limitations;
- approved plan;
- branch and unified diff;
- dbt artifacts and test results;
- rollback evidence;
- native receipt.

## Stop or reframe conditions

- If repository evidence and DataHub cannot identify the same consumer
  reliably, do not mutate from a guessed mapping.
- If useful changes routinely escape bounded files or cannot be validated by
  dbt, narrow the supported repository pattern.
- If code generation becomes the dominant complexity, integrate a stronger
  native coding tool while preserving the campaign preconditions and receipt.

## Risks changed

- R-02 native identity;
- R-03 semantic equivalence;
- R-05 stale source;
- R-06 partial mutation;
- R-09 real execution;
- R-18 idempotency;
- R-24 indirect and generated references;
- R-25 branch movement.
