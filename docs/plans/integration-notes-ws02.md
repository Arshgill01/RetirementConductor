# WS-02 integration notes

WS-02 is implemented on `codex/semantic-pr-agent` without editing the active
campaign files or shared integration documents.

## Delivered

- strict semantic-plan, model-evidence, and GitHub-receipt schemas;
- deterministic safe-primitive validation, digest freezing, approval binding,
  and reviewed dbt test materialization;
- optional Google Vertex AI Gemini planner with forced, bounded read-only
  function calling and redacted native response evidence;
- exact GitHub remote, branch, commit, PR, CI, drift, idempotency, and forbidden
  action controls;
- deterministic mocked adversarial coverage and a real public-safe acceptance
  bundle;
- feature runbook, pinned reference CI workflow, and evidence publisher.

The only shared registration hunk is in `schemas.py`. The small `git_dbt.py`
hunk carries the source dataset URN from fresh DataHub replacement evidence so
semantic field identities do not incorrectly inherit the downstream consumer
URN. No CLI, MCP, Makefile, status, evidence-ledger, architecture, contract,
risk, decision, or campaign-plan integration was attempted on this branch.

## Live acceptance

The public disposable boundary is
`Arshgill01/retirement-conductor-semantic-pr-acceptance`, PR
<https://github.com/Arshgill01/retirement-conductor-semantic-pr-acceptance/pull/1>.
The accepted proposal used `gemini-3-flash-preview` against real DataHub and
dbt evidence and froze `type_compatibility` plus
`exact_model_output_parity`. The final recovered PR receipt binds dbt Core
1.12.0 and dbt-duckdb 1.10.1 to the exact head.

The live DataHub source did not expose glossary or field-quality observations.
Those contexts are represented as `NOT_OBSERVED`, and empty query history is
not treated as closure evidence. The model acceptance artifact is live; mocked
tests remain labeled fixture evidence and are not cited as live proof.

## Integration-owner actions

- Decide whether to expose a CLI/MCP orchestration command after merging the
  new schemas and modules. Keep live model use optional and disabled by default.
- If a shared acceptance target is desired, register the focused WS-02 tests
  and evidence publisher in the integration branch rather than changing the
  workstream Makefile here.
- Preserve the public artifact bundle and sample PR URL when reconciling shared
  status or evidence-ledger documents.
- Re-run `make check` after conflict resolution, especially if Git/dbt plan or
  approval contracts changed in another workstream.
