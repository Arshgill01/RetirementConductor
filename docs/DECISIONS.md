# Decision log

Decisions describe current product and engineering boundaries. Change one by
adding a superseding entry; do not silently rewrite the rationale.

## D-001 — one complete column-retirement vertical

Status: accepted.

Support one warehouse column replaced by one compatible column before adding
other asset types. The product must complete discovery, mutation, validation,
reconciliation, write-back, and the producer-side gate.

Why: broad asset support would hide whether any one lifecycle actually works.

## D-002 — DataHub is context and reconciliation, not transaction storage

Status: accepted.

Use DataHub for cross-system identity, lineage, schema, ownership, shared
campaign context, and final reconciliation. Keep in-progress campaign events
in a small durable local store.

Why: metadata ingestion and search indexing are eventually consistent, and a
document surface does not supply the execution semantics required by a saga.

## D-003 — command line and SQLite first

Status: accepted.

Start with one Python command-line process and SQLite. Do not introduce a
service, queue, or storage abstraction until a demonstrated deployment
requires one.

Why: this is enough for resumability, CI integration, deterministic testing,
and the complete supported path.

## D-004 — deterministic policy owns readiness

Status: accepted.

Model output may propose mappings, patches, and explanations. Deterministic
code owns identity uniqueness, source preconditions, authorization, state
transitions, receipt acceptance, and final decision.

Why: readiness must be reproducible, testable, and resistant to persuasive but
unsupported output.

## D-005 — Git/dbt is the first native executor

Status: accepted.

Use an allowlisted Git branch as the mutation boundary and dbt as the native
validator.

Why: the preceding experiment proved this boundary is real, reviewable, and
capable of semantic tests without production mutation.

## D-006 — Looker is the second heterogeneous executor

Status: accepted, live evidence pending.

Implement one bounded saved-content migration through documented Looker APIs,
then validate with Looker-native surfaces and reconcile through DataHub.

Why: it tests whether the shared campaign and receipt contracts survive a
non-repository system. It also exposes real permission, scope, recovery, and
eventual-consistency problems.

## D-007 — final destructive action remains separately privileged

Status: accepted.

Retirement Conductor produces an enforceable readiness result. The producer
workflow that removes or disables the legacy field uses separate credentials
and must call the gate inside the exact trusted producer invocation immediately
before action. The result is bound to that producer plan and is not reusable.

Why: discovery and consumer-migration credentials should not also have broad
warehouse removal authority.

## D-008 — no general adapter framework before two live implementations

Status: accepted.

Define the minimal lifecycle contract now, but extract reusable libraries only
after Git/dbt and Looker reveal genuinely shared requirements.

Why: an imagined extension system would add complexity while freezing the
wrong abstractions.

## D-009 — deterministic digest now, signing only with a threat model

Status: accepted.

Use canonical JSON and SHA-256 for stable identity and change detection. Record
native provenance separately. Add cryptographic signatures only after signer,
key custody, verification, rotation, and recovery are designed.

Why: a signature without an operational trust model creates confidence without
useful security.

## D-010 — one policy engine for CLI, report, and gate

Status: accepted.

All operator surfaces render the same canonical manifest. No interface may
recompute readiness.

Why: separate policy implementations drift and can produce contradictory
answers.

## D-011 — disappearance is not closure

Status: accepted.

A consumer or edge disappearing during reconciliation does not by itself prove
successful migration. Closure needs a live native receipt, verified removal,
or proved non-applicability.

Why: ingestion filters, stale state, renames, and connector errors can all
remove graph edges without fixing a consumer.

## D-012 — refusal is a successful product outcome

Status: accepted.

`BLOCKED`, `UNSAFE`, and `REVIEW_REQUIRED` remain inspectable, resumable
campaign outcomes. They must include the precise evidence gap or unsafe
consumer.

Why: forcing a positive answer would destroy the system's core value.

## D-013 — SQLite deployment is single-writer

Status: accepted.

One deployment identity owns the active SQLite state directory and campaign
lock. A second runner, copied database, or unsupported shared filesystem must
refuse rather than behave like coordinated state.

Why: local locking cannot establish authority across divergent stores. A
service or distributed store should be introduced only when a real
multi-operator deployment requires it.

## D-014 — uncertain native outcomes require discovery

Status: accepted.

A lost apply response is `OUTCOME_UNKNOWN`, not failure or success. Before
retry or compensation, reread the exact native object. Compensation proceeds
only when the current state still matches the expected post-apply fingerprint;
otherwise preserve the intervening change and remain unsafe.

Why: retrying can duplicate a successful unseen mutation, while blind rollback
can erase another actor's valid edit.

## D-015 — phase 04 proves live permission and refusal

Status: accepted.

The complete first vertical includes two disposable live campaigns: an
isolated all-closed graph that permits one harmless producer sentinel, and a
rich graph whose unresolved external consumers refuse that sentinel.
Deterministic fixtures still cover the full decision matrix but cannot be the
only positive path.

Why: a gate proven green only by a fixture would leave the central live
completion claim untested.

## D-016 — use standard YAML and JSON Schema implementations

Status: accepted.

Use PyYAML only through `safe_load` for the operator specification and use
jsonschema Draft 2020-12 validation for the versioned executable contracts.
Keep canonicalization, digests, semantic cross-field rules, path scope, and
policy in product code.

Why: YAML and JSON Schema have mature edge-case behavior that should not be
reimplemented in the safety boundary. Both runtime dependencies are small,
permissively licensed, pinned in `uv.lock`, and isolated from campaign
authority.
