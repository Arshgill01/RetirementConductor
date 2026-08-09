# TE-02 integration notes — Retirement Gauntlet v2

## Workstream identity

- Branch: `codex/retirement-gauntlet-v2`
- Planning base: `codex/winning-truth-experiments-plan` at `f521a4d`
- Frozen truth commit: `f10a7e3`
- Frozen corpus SHA-256:
  `b0e9c23f0d206e4a8925da578ce6e4fdf315a47b057198b2cc1c4e1fcf9ff03c`
- Frozen oracle SHA-256:
  `ff67034d1b4b6eff85c80dcb94f499dd8e293a5f353f39fbb1ea2ec2a9facdb0`

The oracle was committed before any product campaign case was executed. The
runner verifies the frozen byte digests and has no code path that rewrites the
truth files.

## Shared hunks intentionally deferred

The coordination plan freezes every file below. Integration should apply only
these minimal follow-ups after inspecting the TE-01 through TE-03 reports:

1. `README.md`: link the compact Gauntlet v2 index and state its fixture/live
   evidence boundary.
2. `STATUS.md` and `docs/EVIDENCE_LEDGER.md`: record the tested workstream
   commit, exact commands, public evidence digest, modes, and limitations.
3. `docs/ARCHITECTURE.md` and `docs/CONTRACTS.md`: document
   `REVIEW_REQUIREMENT_RECORDED` and `NON_APPLICABILITY_RECORDED`. A review
   event grants no authority; a non-applicability event accepts only one exact,
   digest-bound consumer/evidence binding.
4. `docs/DECISIONS.md`: record why durable review requirements and explicit
   non-applicability receipts were retained after the gauntlet exposed the two
   unreachable/unevidenced paths.
5. `docs/RISKS.md`: update synthetic circularity and disappearing-lineage risks
   from the corruption and non-applicability probes.
6. `docs/REQUIREMENTS_TRACEABILITY.md`: attach the Gauntlet v2 evidence to
   RC-002, RC-003, RC-005, RC-008 through RC-012, RC-016, RC-019, and RC-020.
7. `Makefile`: add a shared `retirement-gauntlet-v2` target that runs
   `make git-dbt-tool` followed by
   `uv run python -m scripts.run_retirement_gauntlet_v2`.

No semantic-model code, Codex behavior, skill/MCP implementation, packaging
metadata, existing Phase 06 evidence, or submission surface was changed.

## Integration recommendation

`KEEP` the durable campaign/gate boundary. The experiment is intended to test
whether it holds across balanced semantics and hostile sequences, not to add a
second policy engine. Retain the two narrow event types only if the final
evidence has zero false readiness, exact code parity, and no closure without an
evidence receipt. Otherwise mark this recommendation `INCONCLUSIVE` and do not
promote the event changes.

## Evidence classification and retention

- Frozen corpus and oracle: committed deterministic fixture truth.
- DataHub tier: live-local Core and MCP over controlled fixture metadata.
- Git/dbt tier: live-local disposable repositories and dbt validation.
- Raw command/aspect/receipt state: ignored under
  `.retirement-conductor/gauntlet-v2/`; operator-managed retention.
- Public aggregate: `artifacts/public/retirement-gauntlet-v2/index.json`.
- Production and customer-value claims: explicitly not established.

## Final evidence

- Tested behavior commit: `b88affc`
- Runner command:
  `uv run python -m scripts.run_retirement_gauntlet_v2`
- Result: `RETIREMENT_GAUNTLET_V2_PASSED`
- Public evidence digest:
  `sha256:28e8cfc536700232533b92ec67a18a72041be2e8d231a8f59f985fce74fe0220`
- Decisions: 4 `READY_TO_RETIRE`, 6 `BLOCKED`, 10 `UNSAFE`, and 4
  `REVIEW_REQUIRED`; every decision and refusal/review code matched the
  independent oracle.
- Tiers: 24 durable-store cases, 15 live-local DataHub cases, 8 disposable
  Git/dbt cases, and 4 gate/watch sequence cases.
- Controlled recall: 121/121 expected consumers, with zero false readiness
  and zero unexpected closure.
- The deliberately corrupted oracle comparison was rejected.
- One producer action executed in the clean case. The other sequence cases
  refused an unchanged-watch-invalidated plan, a late-consumer-reversed plan,
  and an expired plan.

The READY exemplar was inspected rather than accepted by exit status alone.
Its raw evidence has a complete four-page, 5/5 DataHub inventory; a Git apply
receipt bound to one exact consumer; dbt parse, seed, build, and test commands
with exit code zero; a `VALIDATED` terminal receipt; unchanged reconciliation;
verified DataHub publication; and an `EXECUTED` producer gate receipt. The
compact public index contains no raw repository paths or run token.

## Observed failures and fixes

The successful evidence follows several failure-closed attempts. None of the
failed attempts published a result.

1. A shared DataHub port collision occurred before product execution. The
   runner now uses an isolated Compose project and loopback ports.
2. Eventual-consistency gaps produced transient missing lineage pages and MCP
   transport truncation. Retries are bounded to the affected live read and do
   not turn partial evidence into complete evidence.
3. A full uncached twin traversal exhausted the shared host. The retained twin
   is an independent cache-bypassed paged GMS read, while every live case also
   performs direct schema, lineage, and ownership reads.
4. Partial pagination initially lost controlled identities. The runner now
   retains the frozen controlled identities as opaque under the partial
   envelope, so missing pages block rather than silently erase consumers.
5. Replay-only Git/dbt evidence used a pre-normalization envelope shape. It now
   validates against the current evidence-envelope schema before campaign use.
6. The stale-native-data case initially described only fresh metadata. It now
   records a separate required `native-data` source as `STALE`, preserving the
   fresh DataHub source and producing the frozen refusal through policy.
7. Compose replaced the GMS container during its update lifecycle. Immutable
   image and health provenance is now captured when startup health succeeds,
   before seeding and product execution, rather than by retaining a container
   ID until the end.

These fixes changed the experiment boundary or durable event projection; they
did not change the frozen corpus, oracle, policy rules, or product decision
expectations.

## Validation and inspection

- `uv run ruff check scripts/run_retirement_gauntlet_v2.py tests/unit/test_retirement_gauntlet_v2.py`
  — passed.
- `uv run mypy` — passed for 89 source files.
- `uv run pytest -q tests/unit/test_retirement_gauntlet_v2.py` — 3 passed,
  including the corrupted-oracle rejection and stale-native envelope check.
- `uv run python scripts/check_public_artifacts.py` — passed, 74 files checked.
- `uv run python scripts/check_secrets.py` — passed, 383 text files checked.
- `git diff --check` — passed before the final gauntlet run.
- `make check` — passed: ruff and format checks, mypy over 89 source files,
  247 tests, repository validation, secret and public-artifact scans, source and
  wheel builds, and `git diff --check`.

The final MCP health probe in the compact index is `null`; the server had
already served all 15 live cases, and startup health plus per-case raw MCP/GMS
artifacts prove the exercised boundary. This is a disposable-lifecycle
observation, not production evidence, and should remain a stated limitation.

## Final recommendation

`KEEP` the durable campaign/gate boundary and the two narrow event types. The
promotion criteria above passed. Integration should preserve the frozen-file
boundary and apply the deferred shared-document hunks only after comparing the
TE-01 and TE-03 reports.
