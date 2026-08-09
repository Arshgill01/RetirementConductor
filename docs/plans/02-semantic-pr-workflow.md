# WS-02 — semantic validation planning and GitHub PR boundary

## Objective

Give the model a consequential but non-authoritative role: use DataHub schema,
quality, query, glossary, and lineage context to propose migration-specific
semantic validation, then place the approved exact change into a real GitHub
pull request whose head commit and CI evidence remain bound to the campaign.

This workstream must not introduce a hidden model provider or let arbitrary
model output become executable proof.

## Product result

```text
DataHub context
  -> model proposes a typed semantic validation plan
  -> kernel validates scope and freezes the digest
  -> human approves the exact plan and target
  -> existing Git/dbt boundary applies the change
  -> branch and commit are pushed to an allowlisted remote
  -> one GitHub PR is opened
  -> native dbt validation and CI are bound to the PR head
  -> head drift invalidates the receipt
```

## Phase A — typed semantic validation proposal

Add a versioned schema that supports a deliberately small vocabulary of safe
validation primitives, for example:

- source and replacement type compatibility;
- nullability and null-rate bounds;
- accepted-value coverage;
- explicit category mapping completeness;
- row-count or keyed-row coverage;
- aggregate parity over a declared group and time grain;
- exact affected-model output parity;
- permitted tolerance and freshness window.

Every proposed check must contain:

- target and replacement field identities;
- consumer identity and exact native target;
- evidence references returned by DataHub tools;
- rationale separated from executable parameters;
- expected validator and version family;
- limitations;
- proposal digest.

Do not allow free-form shell commands, arbitrary paths, arbitrary SQL, network
locations, Python, macros, packages, environment variables, or additional
repository targets in the proposal schema.

The kernel must reject:

- a field, consumer, repository, or target that differs from the campaign;
- evidence references absent from the current observation set;
- a validation primitive incompatible with the declared types;
- a tolerance outside policy;
- missing fresh evidence;
- duplicate or contradictory checks;
- metadata text presented as an instruction;
- a proposal created for another plan or source fingerprint.

Materialize accepted primitives through reviewed dbt test templates or safe
adapter-native parameters. The exact generated test files and targets join the
plan digest and approval boundary.

## Phase B — real GitHub pull request

Add one concrete GitHub boundary for the existing Git/dbt executor. Use `git`
and authenticated `gh`; do not add a second generic source-control abstraction.

Required controls:

- explicit opt-in configuration for push and PR creation;
- exact allowlisted remote identity and repository;
- dedicated branch prefix;
- clean expected base branch and source commit;
- no force push, deletion, merge, review approval, or branch-protection change;
- no credential values in arguments, logs, artifacts, or campaign state;
- exactly the files named by the approved plan;
- commit identity and tree digest captured after local validation;
- PR number, URL, base, head, head SHA, and changed-file set captured from a
  native reread;
- idempotent reuse of the same campaign PR rather than duplicate PR creation;
- outcome-unknown handling for push or PR transport loss.

CI evidence must identify the exact PR head SHA, workflow/check name, run ID,
conclusion, validator versions where available, and captured timestamp. A
green unrelated check is not dbt validation. A PR head change makes the
campaign receipt stale until the exact new head is replanned, reapproved, and
revalidated.

The agent may propose and request PR creation. It may not merge the PR or
approve its own change.

## Suggested implementation ownership

Prefer new files:

- `schemas/semantic-validation-plan-v1.schema.json`;
- `src/retirement_conductor/semantic_validation.py`;
- `src/retirement_conductor/github_pr.py`;
- `src/retirement_conductor/github_pr_config.py`;
- focused unit and integration tests;
- one feature-specific runbook and evidence generator.

Keep changes to `agent_mcp.py`, `cli.py`, `git_dbt.py`,
`git_dbt_workflow.py`, `schemas.py`, `pyproject.toml`, and `Makefile` as small
registration or orchestration hunks. Record shared controlling-document edits
for the integration owner rather than rewriting them on this branch.

## Live acceptance

Use a disposable public-safe GitHub repository or an explicitly disposable
branch in an authorized repository.

Prove:

1. the model reads real DataHub context and proposes at least two relevant
   semantic checks;
2. the kernel rejects one irrelevant or unsafe proposal;
3. the accepted plan freezes exact dbt model and test targets;
4. apply refuses before external authorization;
5. the exact approved change and tests are committed and pushed;
6. one real PR opens with the expected file set;
7. dbt-native validation passes for the exact PR head;
8. the PR and validation receipt are recorded without secrets;
9. a subsequent commit to the PR invalidates the accepted head and refuses
   readiness;
10. restoration or a fresh replan can recover without overwriting an owner
    change.

Publish a sample PR, redacted semantic plan, exact diff, native receipt, CI
binding, and head-drift refusal.

## Required adversarial cases

- prompt injection in a DataHub description;
- a model proposal naming a second file;
- arbitrary SQL or shell in the validation proposal;
- wrong plan digest;
- missing human approval;
- remote mismatch;
- pre-push source drift;
- push outcome unknown;
- duplicate PR retry;
- CI result for the wrong SHA;
- new commit after validation;
- attempt to merge or self-approve through the agent.

## Stop conditions

Stop rather than weaken scope if:

- safe semantic checks require executing arbitrary model-generated SQL;
- the exact DataHub evidence cannot be bound into the proposal;
- PR creation cannot be made idempotent;
- CI cannot be tied to the exact head SHA;
- the implementation treats PR or CI success as semantic proof;
- live GitHub acceptance cannot be performed on an authorized disposable
  boundary.
