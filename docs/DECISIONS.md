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

## D-017 — event replay is authoritative over materialized state

Status: accepted.

Commit each validated event before updating the cached manifest. On restart,
verify the event sequence, predecessor chain, and digests, then repair a cache
only when it is an intact prefix of the authoritative replay. Refuse a cache
whose own digest fails or whose history diverges.

Why: a crash after event commit can legitimately leave a stale cache, while
silently accepting arbitrary cache divergence could manufacture readiness.

## D-018 — select DataHub surfaces from live capabilities

Status: accepted from DataHub Core v1.6.0 evidence.

Use the self-hosted MCP server for catalog search, schema, lineage context,
ownership, permitted query context, exact paths, and stable document writes.
Use supported GMS GraphQL for fully counted lineage pagination, exact document
read-back and identity search, and lifecycle observation when the live MCP
surface is incomplete or conditional. Record the selected surfaces and the
available mutation names in a capability fingerprint, but never infer
permission from schema visibility.

The initial adapter does not invoke `updateDeprecation` or any equivalent
lifecycle mutation. Core's missing `isPartial` signal remains a limitation
even when returned and advertised counts match.

Why: on the observed Core/MCP versions, MCP document read tools were
conditional and generic entity read-back returned only the document URN,
while GraphQL exposed the exact supported document and pagination fields.
Binding the adapter to observed capabilities preserves complete evidence
without pretending that Core and Cloud expose the same tool union.

## D-019 — cross-source scope expansion uses a conservative minimum

Status: accepted from phase 02 evidence.

Until native identity binding proves overlap between repository and catalog
consumers, report catalog expansion as a lower bound. Subtract every
configured repository match from the graph count as if it overlaps a distinct
graph consumer. Keep the overlap unknown and label the observation as scope
comparison only; it cannot authorize mutation or closure.

Why: calling every graph entity “additional” would silently assume that no
repository consumer represents the same object. The conservative minimum
still proved material expansion in the representative graph without
manufacturing cross-source identity.

## D-020 — Git/dbt mutation requires an explicit cross-source identity

Status: accepted from phase 03 evidence.

Authorize the first repository mutation only when one dbt manifest node
explicitly declares a DataHub URN that appears in the fresh campaign inventory.
Bind that match to the dbt unique ID, original file path, repository identity,
branch, commit, and content fingerprint. Do not infer mutation authority from
display names, text similarity, ownership, or lineage position.

Why: the live graph and repository described the same consumer reliably only
after exact manifest metadata joined their identities. Text and compiled SQL
remain useful discovery layers, but neither proves which graph consumer is the
authorized native object.

## D-021 — validate untrusted dbt projects from a copied no-network boundary

Status: accepted from phase 03 evidence.

Run the pinned dbt toolchain against a copied project tree inside bubblewrap
with an unshared network, no host home, no source-repository mount, an
allowlisted environment, and explicit time, file, process, memory, and open-file
bounds. Refuse symlinks and external dbt dependencies in the initial adapter,
and force Git hooks and global/system configuration out of the mutation path.

This is the supported Linux validation boundary, not a claim that arbitrary
dbt projects are safe on every host. A deployment without an equivalent
isolation mechanism refuses native validation.

Why: dbt models, macros, dependencies, Git configuration, and hooks are
repository-controlled code. Running them in the agent's ordinary environment
would expose credentials and files that the campaign never authorized.

## D-022 — issue and consume one producer plan per canonical manifest

Status: accepted from phase 04 evidence.

The campaign writer durably issues one exact, short-lived producer plan for
one canonical manifest. Gate execution accepts only byte-equivalent issued
content, records intent before action, and consumes both the plan and
campaign/manifest binding. A refusal that performs no action remains
retryable; an executed or outcome-unknown action cannot be replayed. A newly
computed plan for the same manifest is not an authorization.

Why: a ready manifest is evidence, not a bearer token. Durable issuance closes
the gap between planning and execution, while intent-before-action and
one-time consumption prevent duplicate producer changes after retries or lost
responses.

## D-023 — page sparse DataHub lineage by individual degree

Status: accepted from DataHub Core v1.6.0 phase 04 evidence.

Query downstream lineage separately for degree `1`, `2`, and `3+`, page each
bucket to its advertised total, then union and de-duplicate the results.
Treat duplicate entities, changing totals, failed pages, or count mismatch as
partial evidence.

Why: the live Core boundary returned only degree-one results when multiple
degree values were supplied together for a sparse graph, even though the
degree-two late consumer existed. Independent buckets exposed that consumer
and allowed it to reopen readiness without assuming a complete multi-value
filter.

## D-024 — apply confirmation binds the reviewed plan digest

Status: accepted from phase 05 evidence.

Require the operator to pass the exact current plan digest at apply time in
addition to the campaign's durable approval. Missing confirmation refuses as
`AUTH_APPROVAL_MISSING`; a different digest refuses as
`AUTH_APPROVAL_WRONG_PLAN`. The confirmation cannot alter the approved target
set, source fingerprint, capability, authority, or expiry.

Why: a stored approval proves authority for one plan, but it does not prove
that the person invoking mutation reviewed the current command output. An
explicit digest makes the plan/apply boundary visible without turning a
free-form prompt into authorization.

## D-025 — operator explanations remain canonical and public redaction is structural

Status: accepted from phase 05 evidence.

Validate the canonical manifest and digest, reduce it through one shared
presentation model, and render every terminal and HTML view from that model.
New review-required manifests carry their explicit review reasons; schema
version 1 omits an empty `review_requirements` field to preserve previously
issued digests.

Build public export from a structurally redacted presentation model rather
than scrubbing completed HTML. Retain decision, digest, counts, bounded
coverage, and recovery shape while replacing source and native identities.
The private manifest remains the integrity authority.

Why: duplicated policy or post-hoc string scrubbing could make the interface
disagree with the gate or leak an unanticipated field. Preserving historical
digests also matters more than normalizing an optional empty array.

## D-026 — Looker mutation changes one saved Look by immutable query identity

Status: accepted for the deterministic adapter contract; live evidence
pending.

Treat the supported Look identity as the numeric content ID together with its
`content_metadata_id` and `created_at`, bound to platform instance, project,
model, Explore, folder, and exact DataHub URN. Create or reuse the immutable
replacement query through `POST /queries`, then change only the saved Look's
`query_id` through the documented PATCH surface.

Write a durable intent before mutation. Never retry a mutating request
automatically. A missing response remains outcome unknown until the exact
native identity and before/after fingerprints are reread. Compensation also
rereads and refuses rather than overwriting any intervening edit.

Why: a numeric ID or title can be reused after deletion, and a successful or
failed HTTP response alone cannot prove the native state. Query immutability
keeps the approved content change inspectable while the one-property PATCH
keeps target scope narrow.

## D-027 — cross-source inventory extension preserves closure conservatively

Status: accepted from deterministic campaign integration; live Looker evidence
pending.

When a second native adapter joins an existing campaign, union its fresh
consumer membership through `INVENTORY_EXTENDED` without erasing earlier
plans or accepted receipts. Any prior evidence source not reread during that
extension becomes `STALE`. Final reconciliation rereads both native sources
under their original identity, permission, and traversal scopes.

If one native reread fails, invalidate and stale only that consumer's receipt;
retain the unrelated validated receipt and mark the failed source stale in the
combined envelope.

Why: replacing the entire inventory would lose durable work, while carrying
unobserved sources forward as fresh would manufacture equivalent coverage.
Selective invalidation lets one campaign remain honest across heterogeneous
systems.

## D-028 — Looker ingestion uses separate API and LookML recipes

Status: accepted from DataHub 1.6.0 configuration and local fixture parsing;
live saved-content ingestion pending.

Use the official DataHub `looker` source for one anchored saved Look and the
official `lookml` source for its local project and column lineage. The API
recipe excludes dashboards, personal folders, usage history, and embed URLs,
uses one worker, and keeps stateful ingestion enabled for the disposable
delete/recreate probe. The LookML recipe uses an explicit local project and
connection-to-platform map with partial lineage disabled; it does not request
an admin API credential for view lineage. Its narrow disposable contract fixes
the connection key to `retirement_fixture`, because the pinned DataHub runtime
expands environment references in values but not mapping keys.

During reconciliation, query the legacy and replacement fields separately.
Recognize a field edge only when the exact consumer URN has a matching
column-lineage claim object. Preserve table-only lineage as an explicit
connector limitation and never infer closure from disappearance.

Why: API content metadata and parsed LookML supply different parts of the
identity and lineage chain. Combining them through explicit recipes preserves
their provenance without turning either weaker table visibility or System
Activity usage queries into field-level proof.

## D-029 — LookML ingestion completion requires direct aspect reread

Status: accepted from local DataHub Core v1.6.0 observation.

Use a synchronous DataHub sink, require positive source events with no dropped
model or view and no reported warning or failure, then reread the exact stored
schema and upstream-lineage aspects. Only the reread can establish that the
expected fields and field-level edges exist. Preserve connector counters and
messages as diagnostics, not as the authority for completion or absence.

Why: the official 1.6.0 LookML source emitted 20 events and stored the exact
entity and three field-lineage edges while also setting its no-event flag,
logging a no-metadata message, and reporting zero sink records. Accepting
either the success exit or the contradictory counter alone would violate the
empty-result and inspected-evidence rules.
