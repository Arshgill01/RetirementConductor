# Execution status

This is the current implementation state. Update it after evidence is
inspected, not when work merely starts. `GOAL.md` defines the completion
contract; `PLAN.md` defines proof order.

## Current state

- Execution state: complete for the credential-independent engineering goal in
  `GOAL.md`; no adoption or customer-value claim is implied
- Active phase: none
- Current integrated behavior commit: `b027c58`; installed-reference lifecycle
  fix: `0db89e2`; packaged-agent acceptance: `4c1d397`
- Current complete full-run evidence commit: `ea021ff`
- Current external blocker: none for the overnight engineering goal; the
  independent-operator observation remains honest follow-on adoption evidence
- Next acceptance target: record the public three-minute product run and finish
  the Devpost entry. Optional independent-operator evaluation for RC-018
  remains `NOT_RUN` and blocks any adoption claim, not this engineering goal.
- Last integrated repository validation: 242 tests, Ruff, formatting, strict
  mypy over 88 source files, 200-file repository validation, 369-file secret
  review, 73-file public-artifact review, reproducible source and wheel builds,
  and `git diff --check` passed. Four clean Python installs, upgrade/rollback,
  removal, and the installed-wheel live-local reference passed. A separate
  clean Python 3.13 install of the `agent` extra completed a real MCP handshake
  and exposed exactly 16 tools from the packaged wheel.
- Agent-path validation: behavior commit `0d70db9` produced an ephemeral Codex
  MCP trace with exactly the two declared tools, no shell calls, the retained
  live late-consumer decision `UNSAFE`, and no producer-action attempt. The
  preceding implementation commit passed 189 tests plus Ruff, formatting,
  strict mypy, repository validation, scans, package builds, and
  `git diff --check`. The evidence-promotion worktree then passed 190 tests,
  191-file repository validation, 332-file secret and 57-file public-artifact
  scans, reproducible package builds, and `git diff --check`.
- Complete agent-path evidence: behavior commit `de5f895` produced a real
  five-stage Codex run over disposable live-local DataHub and Git/dbt. The
  product agent inspected DataHub, planned one exact target, stopped for
  external authorization, applied and natively validated the dbt change,
  reconciled, published and verified the summary, issued a short-lived
  Retirement Lease, and executed a harmless sentinel. Fresh reconciliation
  after a late Spark consumer then reversed `READY_TO_RETIRE` to `UNSAFE`; no
  second lease or gate call occurred. This was a user-directed author/operator
  run, so RC-018 remains honestly `NOT_RUN`.
- Integrated post-goal workstreams: a live Vertex Gemini advisory planner
  produced a typed proposal that deterministic code bound to an exact public
  GitHub PR and passing CI; continuous reconciliation invalidated an already
  issued Retirement Lease from a fresh late DataHub field edge; and a bounded
  Superset 6.0.0 experiment proved one native mutation, validation,
  reingestion, compensation, and owner-drift refusal. The first two are
  integrated product capabilities. Superset remains explicitly experimental
  and cannot affect canonical campaign readiness or the producer gate.

## Phase ledger

| Phase | State | Direct evidence | Remaining boundary |
|---|---|---|---|
| 00 | complete | `EP-000` at `6692a3c`; strict schemas, 24 tests, eight refusal fixtures, clean wheel smoke test | none |
| 01 | complete | `EP-001` at `30173f1`; 85 tests, SQLite replay parity, interruption and refusal matrix | none |
| 02 | complete | `EP-002` at `19bebb9`; live Core resolved both fields, returned 31 consumers over seven pages, proved at least 30 beyond configured repository scope, and verified four updates to one document URN without lifecycle mutation | none |
| 03 | complete | `EP-003` at `3ca39a1`; exact live DataHub-to-dbt mapping, two one-file applies, native validation receipt, verified rollback, idempotent retry, and contained adversarial probes | none |
| 04 | complete | `EP-004` at `25466a9`; equivalent live reconciliation, verified stable publication, one issued-plan sentinel, live late-consumer reopening, rich-graph refusal, and adversarial gate matrix | no production warehouse deletion was attempted |
| 05 | complete | `EP-005` at `ae62486`; four-decision CLI, deterministic canonical reports, exact plan confirmation, structural public redaction, keyboard/mobile browser proof, and zero axe violations | independent nontechnical operation remains phase 08 evidence |
| 06 | complete | checkpoint B at `4148020` pins four official assets; C at `ef02788`/`6c9d4aa` generates deterministic quality truth; D/E at `34df09e` and post-removal confirmation at `8f5eb58` directly reread live Core aspects, matched 14/14 independent scenarios with zero false readiness, passed exact Git/dbt and three native fault probes, verified one publication and sentinel, and refused late/rich graphs across three semantically equivalent runs | none for the benchmark; production coverage remains explicitly unclaimed |
| 07 | complete | post-removal evidence at `6e4ca87`: 53 security, 47 fault, and 40 recovery tests; plan-only refusal; manifest-preserving backup/restore; copied-store refusal; zero dependency findings; secret and public scans; binding to Phase 06 zero-false-readiness evidence | production host, secret provider, and distributed storage controls remain operator-owned |
| 08 | complete | post-removal engineering evidence at `c3440b2`: reproducible 0.2.0 package, four clean Python installs, actionable preflight, upgrade/rollback/removal, and 35 installed-wheel operations completing ready, late, and rich live-local Core paths | RC-018 independent operation and customer-value evidence remains follow-on `NOT_RUN` |

Allowed states are `queued`, `active`, `access-dependent`, `blocked`,
`complete`, and `reframed`. At most one phase is `active`. A phase can return
to `active` if later evidence invalidates its acceptance result.

## External boundary queue

| Boundary | Needed now | Current disposition | Controlling document |
|---|---|---|---|
| DataHub Core | no | agent may start a disposable local instance | `docs/ACCESS.md` |
| Git/dbt target | no | agent may create disposable local resources | `docs/ACCESS.md` |
| Official hackathon datasets | no | public CC0/public-domain inputs may be downloaded to an ignored cache only after revision, license, and checksum verification | `GOAL.md` |
| Looker | no | removed from the supported product and completion contract; do not provision, authenticate, ingest, query, or mutate it | `GOAL.md` |
| Independent operator | not for the overnight engineering goal | one prospective operator must still provide real adoption evidence before any customer-value claim | `docs/ACCESS.md` |

The current work is fully credential-independent. Do not substitute official
or generated fixtures for customer-value evidence, and do not reintroduce a
paid native integration merely to increase platform count.

## Update rule

Whenever a phase state changes:

1. link direct evidence in `docs/EVIDENCE_LEDGER.md`;
2. record the tested commit and evidence mode;
3. update changed risks and decisions;
4. name any remaining external boundary precisely;
5. run `make check`;
6. commit this file with the behavior and evidence it describes.
