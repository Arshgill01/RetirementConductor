# Semantic validation planner and GitHub PR boundary

This runbook covers the optional WS-02 model proposal boundary and the
deterministic GitHub pull-request workflow. The model is advisory. It cannot
authorize a write, accept validation, merge or approve a pull request, or
decide retirement readiness.

## Boundary

The supported sequence is:

```text
fresh DataHub + dbt evidence
  -> bounded read_datahub_context and read_dbt_context calls
  -> typed semantic proposal through forced function calling
  -> deterministic identity, evidence, policy, and digest validation
  -> external approval of the exact model and generated test files
  -> deterministic Git/dbt apply and reviewed test materialization
  -> exact commit, non-force push, one idempotent GitHub PR
  -> native dbt validation and named GitHub check on the exact PR head
```

The safe primitive vocabulary is defined in
`semantic-validation-plan-v1.schema.json`. The model never supplies SQL,
shell, Python, packages, macros, environment variables, URLs, arbitrary paths,
or additional repository targets. Reviewed deterministic templates in
`semantic_validation.py` materialize supported checks after approval.

The only model tools are read-only and campaign-bounded:

- `read_datahub_context` returns the current schema, lineage, quality, query,
  glossary, ownership, limitations, and evidence references;
- `read_dbt_context` returns the exact repository commit, manifest identity,
  consumer target, validator versions, and supported checks;
- `submit_semantic_validation_proposal` submits typed data to the deterministic
  kernel and has no write or authorization capability.

Metadata descriptions are untrusted data. Missing quality, glossary, or query
evidence remains missing; the planner may not infer it.

## Optional Google model

WS-02 uses Google Vertex AI `generateContent`, not the OpenAI API. The default
is `gemini-3-flash-preview` because the bounded proposal task does not require
the more expensive Gemini 3.6 Flash tier. Model and pricing availability can
change; verify the current official
[Vertex AI function-calling documentation](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/function-calling)
and [Google pricing](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing)
before changing the default.

Live calls are disabled unless all configuration is explicit:

```bash
export SEMANTIC_MODEL_PROJECT=my-disposable-project
export SEMANTIC_MODEL_LOCATION=global
export SEMANTIC_MODEL_ID=gemini-3-flash-preview
export SEMANTIC_MODEL_ALLOW_LIVE=true
```

Authentication uses `gcloud auth print-access-token` in memory. The access
token is never placed in arguments, logs, artifacts, campaign state, or the
model evidence. Snap-dispatched `gcloud` paths are preserved rather than
resolving the multiplexer symlink.

The redacted model evidence records only native response identifiers, the
resolved model, prompt/evidence/proposal digests, aggregate token counts,
digest-only tool trace, kernel acceptance or refusal, and the non-authority
flags. Model content, thought signatures, and hidden reasoning are not
published.

## GitHub configuration

Use only a disposable public-safe repository or explicitly disposable branch.
The exact repository and remote URL must agree:

```bash
export GITHUB_PR_REPOSITORY_ROOT=/absolute/path/to/disposable-repository
export GITHUB_PR_REPOSITORY=owner/repository
export GITHUB_PR_ALLOWED_REMOTE_URL=https://github.com/owner/repository.git
export GITHUB_PR_BASE_BRANCH=main
export GITHUB_PR_BRANCH_PREFIX=codex/semantic-pr-
export GITHUB_PR_REQUIRED_CHECK_NAME=semantic-dbt
export GITHUB_PR_ALLOW_PUSH=true
export GITHUB_PR_ALLOW_CREATE=true
```

The boundary permits push, PR creation, and native rereads only. It refuses
force push, branch deletion, merge, self-approval, and protection changes.
Transport loss is outcome-unknown until an exact native reread proves the
expected remote head or PR identity.

The reference workflow is
`fixtures/semantic-pr-github/semantic-dbt.yml`. It pins its actions, dbt Core
1.12.0, and dbt-duckdb 1.10.1, then runs parse, seed, build, and test. Receipt
capture reads the exact check run and, when necessary, extracts only the
public validator-version marker from the native Actions log.

## Evidence and recovery

The inspected live acceptance bundle is under
`artifacts/public/semantic-pr/`. It includes the public sample
[PR #1](https://github.com/Arshgill01/retirement-conductor-semantic-pr-acceptance/pull/1),
redacted model evidence, frozen semantic plan, exact diff, native receipt, CI
binding, pre-authorization refusal, head-drift refusal, and recovery record.

Publish an inspected private run with:

```bash
uv run python scripts/publish_semantic_pr_evidence.py \
  --repository /absolute/path/to/disposable-repository
uv run python scripts/check_public_artifacts.py
uv run python scripts/check_secrets.py
```

A new PR-head commit invalidates an accepted receipt. Do not overwrite the
owner commit or reuse the stale receipt. Restore by a compensating commit or
create a fresh plan, obtain fresh external approval, rerun native validation
and the exact-head CI check, and emit a new receipt.

The sample evidence is bounded: DataHub returned real schema and paginated
lineage, but no glossary association or field-quality assertion, and empty
query history was explicitly non-authoritative. The sample PR remains open and
unmerged.
