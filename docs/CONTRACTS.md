# Core contracts

These contracts define the minimum shared language between the campaign
engine, DataHub boundary, Git/dbt execution boundary, operator views, and producer-side
gate. They are behavioral contracts first. Executable schemas are created in
phase 00 and versioned independently.

## Contract principles

- Inputs are explicit; no system or permission scope is inferred silently.
- Identities are resolved from live systems and tied back to the supplied
  intent.
- Every evidence claim names its source, capture time, source version, scope,
  and limitations.
- Every action has a frozen plan, source precondition, exact target set, and
  authorization reference.
- Every accepted migration has a source-native validation receipt.
- Every final decision is deterministic for the same policy and evidence.
- Missing, stale, ambiguous, partial, or untrusted data prevents promotion.

## Retirement specification

The operator declares one legacy field and one replacement field:

```yaml
api_version: retirement-conductor/v1alpha1
kind: column_retirement
campaign:
  id: ret-orders-legacy-status
  name: Replace legacy order status
target:
  datahub_urn: null
  platform: snowflake
  instance: production
  database: analytics
  schema: commerce
  table: orders
  field: legacy_status
replacement:
  datahub_urn: null
  platform: snowflake
  instance: production
  database: analytics
  schema: commerce
  table: orders
  field: order_status
evidence:
  datahub:
    required: true
    direction: downstream
    max_hops: 5
    platform_filters: []
    maximum_age_seconds: 900
  repositories:
    - id: analytics
      path: /workspace/analytics
      branch: main
      required: true
  query_history:
    required: false
    requested_window_days: 30
authorization:
  mode: plan
  allowed_repositories:
    - analytics
  allowed_paths:
    - models/
  allowed_native_objects: []
validation:
  required_receipt_types:
    - dbt
policy:
  id: default-column-retirement
  version: 1
```

Rules:

- `datahub_urn: null` means resolve through live search and verify every native
  identity component before use. It never means predict a URN.
- The target and replacement must be different.
- The supported initial path requires the same platform, instance, database,
  schema, and table. A cross-table replacement requires an explicit later
  contract.
- `mode: plan` cannot mutate a source.
- `mode: apply` requires a separate authorization record bound to the campaign
  digest, source versions, and target allowlist.
- A query-history window is the requested scope; the receipt must record the
  actual retention and result coverage exposed by the source.

## Evidence envelope

The envelope is the boundary of every readiness claim:

```json
{
  "schema_version": "1.0.0",
  "captured_at": "RFC-3339 timestamp",
  "sources": [
    {
      "id": "datahub",
      "required": true,
      "status": "COMPLETE",
      "source_version": "server and client versions",
      "identity": "safe instance identifier",
      "scope": {
        "direction": "downstream",
        "max_hops": 5,
        "filters": [],
        "pages": 4,
        "reported_total": 35,
        "returned_total": 35
      },
      "freshness": {
        "observed_at": "RFC-3339 timestamp",
        "source_updated_at": "RFC-3339 timestamp or null",
        "maximum_age_seconds": 900
      },
      "permissions": {
        "principal": "safe principal identifier",
        "effective_scope": "description without secrets"
      },
      "limitations": [
        "query-history retention was not reported"
      ],
      "artifact_ids": [
        "sha256:..."
      ]
    }
  ],
  "envelope_digest": "sha256:..."
}
```

Source status is one of:

- `COMPLETE`: the declared request terminated normally and all advertised
  pages or results were captured;
- `PARTIAL`: the source reported truncation, timeout, inaccessible branches,
  or another explicit gap;
- `UNKNOWN`: completeness cannot be established;
- `UNAVAILABLE`: the source could not be queried;
- `STALE`: evidence exceeded policy freshness.

A required source must be `COMPLETE` and fresh before readiness. `COMPLETE`
describes the declared request, not global visibility.

Complete DataHub lineage paging sets the supported GraphQL
`SearchFlags.skipCache` flag, preserves both the redacted request and raw
response by digest, and records whether the server exposed cache freshness.
If the server reports `cached: true` despite the bypass, the source is
`PARTIAL`. A missing freshness field remains an explicit limitation. The MCP
field-lineage helper has no cache-bypass input in the supported version, so it
may qualify a consumer claim but cannot remove any consumer from the
cache-bypassed GMS result set.

## Evidence claim

Normalized claims never erase raw observation:

```json
{
  "claim_id": "claim-...",
  "type": "CONSUMER_DEPENDS_ON_FIELD",
  "subject": "native or DataHub identity",
  "object": "target field identity",
  "source_id": "datahub",
  "observed_at": "RFC-3339 timestamp",
  "source_version": "version",
  "confidence_basis": "canonical_lineage_edge",
  "artifact_ids": ["sha256:..."],
  "limitations": []
}
```

Confidence basis is categorical evidence provenance, not a model-generated
percentage. Initial values are:

- `canonical_lineage_edge`;
- `column_lineage_edge`;
- `lineage_path`;
- `observed_query`;
- `dbt_manifest_reference`;
- `parsed_repository_reference`;
- `text_reference`;
- `native_platform_reference`;
- `owner_statement`.

An `owner_statement` may route or waive work under policy. It cannot become
native validation.

## Consumer identity

Every consumer has:

- a stable campaign consumer ID;
- zero or one DataHub URN;
- one source domain;
- zero or one exact native identity;
- all evidence claims that caused inclusion;
- an owner set with provenance;
- a current disposition;
- a source version or reason it cannot be versioned.

Identity mapping must be one-to-one for mutation. Zero or multiple native
matches yield `UNRESOLVED`.

Aliases and display names may assist discovery, but they cannot authorize
apply.

## Native execution and external receipts

The automated Git/dbt boundary implements this lifecycle without hiding
source-specific semantics. A future native executor must satisfy the same
safety properties before entering the supported product; DataHub-observed
non-repository consumers remain opaque or externally receipted in the current
scope.

### `preflight`

Input:

- specification digest;
- source configuration references;
- requested capability.

Output:

- authenticated safe principal identity;
- effective read, plan, apply, validate, and compensate capabilities;
- source and adapter versions;
- scoped refusal when a capability is absent.

### `discover_identity`

Input:

- DataHub consumer identity and evidence claims.

Output:

- exact native identity;
- mapping evidence;
- zero, one, or multiple match count.

### `snapshot`

Output:

- normalized mutable state;
- source version;
- content fingerprint;
- related schedule or dependency set;
- recovery material reference;
- raw artifact references.

### `plan`

Output:

- legacy and replacement references;
- exact proposed target set;
- proposed operations;
- required validators;
- predicted rollback or compensation;
- plan digest.

Planning never mutates.

### `apply`

Required inputs:

- approved plan digest;
- approval bound to that digest;
- exact operator-confirmed current plan digest;
- original source version and fingerprint;
- exact target allowlist;
- explicit apply capability.

Output:

- actual target set;
- native request or change IDs;
- before and after fingerprints;
- partial-failure state;
- raw artifact references.

The executor rereads source and scope immediately before apply. Any mismatch
refuses without mutation. Missing confirmation and a confirmation for any
other plan are separate stable authorization refusals; an approval alone does
not imply that the operator reviewed the current native scope.

If transport loss, timeout, cancellation, or process interruption makes the
native result unknown, the adapter records `OUTCOME_UNKNOWN`. It must discover
the actual native state and reconcile intended versus actual targets before
retrying. It may not convert a retry into a fresh unbound operation.

### `validate`

Output:

- exact native command or API operation;
- validator version;
- input scope;
- result and relevant counts;
- safe semantic comparison when configured;
- artifact references.

Validation is `PASSED`, `FAILED`, or `INCONCLUSIVE`. Only `PASSED` can support
`VALIDATED`.

### `compensate`

Output:

- whether recovery was available;
- attempted operations;
- actual restored state;
- verification result;
- remaining manual action.

Compensation rereads the native object and requires the expected post-apply
identity and fingerprint. If another actor changed it after apply,
compensation must not overwrite that change. The campaign records an unsafe
conflict requiring source-native recovery.

Compensation failure or conflict is retained as a first-class blocker.

### `emit_receipt`

The receipt is rejected unless every referenced artifact exists, the target
set matches the approved plan, digests verify, and the terminal disposition is
legal.

### `reconcile_source`

Required inputs:

- exact plan, apply record, and accepted receipt;
- a native reread constrained by the plan's immutable identity;
- fresh, fully paged DataHub snapshots for the legacy and replacement fields;
- the same declared source identity, traversal scope, and effective principal.

The executor reruns dbt-native validation and the replacement-compatibility
check. It verifies that the current repository, commit, file, manifest node,
and compiled source still match the exact post-apply state. Branch movement,
path or source drift, validator failure, receipt mismatch, or a remaining
exact legacy field edge invalidates only that consumer's receipt and makes it
`STALE`.

The graph observation distinguishes:

- `FIELD_EDGE_PRESENT`: the exact consumer URN has a column-lineage claim for
  the resolved field;
- `TABLE_EDGE_ONLY`: canonical lineage contains the consumer, but field
  dependency remains unproven;
- `NOT_OBSERVED`: the consumer is absent within the recorded complete scope.

Only native validation plus an exact replacement field edge supports a graph
closure statement. Table-only lineage is retained as a connector limitation.
Disappearance alone never closes a consumer.

## Consumer receipt

A receipt contains:

```json
{
  "schema_version": "1.0.0",
  "receipt_id": "receipt-...",
  "campaign_id": "ret-orders-legacy-status",
  "consumer_id": "consumer-...",
  "datahub_urn": "urn:li:...",
  "native_identity": {},
  "adapter": {
    "name": "git-dbt",
    "version": "version",
    "mode": "live"
  },
  "source_before": {
    "version": "Git SHA or native version",
    "fingerprint": "sha256:..."
  },
  "plan": {
    "digest": "sha256:...",
    "proposed_targets": [],
    "approved_targets": []
  },
  "apply": {
    "result": "APPLIED",
    "actual_targets": [],
    "before_fingerprint": "sha256:...",
    "after_fingerprint": "sha256:...",
    "native_change_ids": []
  },
  "validation": {
    "result": "PASSED",
    "validator": "dbt build",
    "validator_version": "version",
    "artifact_ids": []
  },
  "compensation": {
    "available": true,
    "exercised": false,
    "result": "NOT_NEEDED"
  },
  "captured_at": "RFC-3339 timestamp",
  "expires_at": "RFC-3339 timestamp or null",
  "limitations": [],
  "terminal_disposition": "VALIDATED",
  "receipt_digest": "sha256:..."
}
```

`mode` is `live`, `fixture`, or `replay`. Policy requiring live evidence
rejects the other modes.

## Campaign state

Lifecycle:

```text
PROPOSED
  → INVENTORIED
  → MIGRATING
  → RECONCILING
  → READY
  → RETIRED
```

`BLOCKED` is reachable from every pre-retirement state. A blocked campaign may
return to `INVENTORIED`, `MIGRATING`, or `RECONCILING` after new evidence. A
retired campaign is immutable; corrections create a linked follow-up record.

Before migration begins, a newly captured baseline may append another
`INVENTORY_RECORDED` event while remaining `INVENTORIED`. It replaces the
current consumer baseline and resets reconciliation, but preserves every
earlier snapshot digest and event. It cannot import a closure disposition.

After one native adapter has already produced campaign evidence,
`INVENTORY_EXTENDED` may add consumers observed by a fresh bounded source
without erasing existing plans or receipts. It is legal only while
`INVENTORIED`, `MIGRATING`, or `BLOCKED`; it unions consumer membership,
replaces the evidence envelope, appends the snapshot digest, and resets
reconciliation. It cannot import a closure disposition. Any prior source not
reread as part of the extension must be marked `STALE` rather than carried
forward as fresh.

Consumer dispositions:

- `DISCOVERED`
- `IDENTIFIED`
- `CHANGE_PROPOSED`
- `APPLIED`
- `VALIDATED`
- `REMOVED`
- `NOT_APPLICABLE`
- `WAIVED`
- `OPAQUE`
- `UNRESOLVED`
- `STALE`
- `FAILED`

Default closure accepts only:

- `VALIDATED`;
- `REMOVED`, with verified native absence;
- `NOT_APPLICABLE`, with evidence that the observed dependency cannot execute.

`WAIVED` requires a named authority, explicit residual risk, bounded scope,
expiration, and a policy that permits it. It remains visibly different from a
successful migration.

DataHub publication performs one idempotently bound write. Agent-visible
read-back may be retried within a fixed bound because indexing is eventually
consistent, but every transient refusal remains evidence and the write is not
repeated merely to obtain visibility. A successful write response is never a
substitute for exact read-back.

## Final decision

The policy produces exactly one:

- `READY_TO_RETIRE`: all required evidence is complete and fresh, every
  in-scope consumer has an accepted disposition, and reconciliation found no
  new consumer;
- `REVIEW_REQUIRED`: evidence is technically sufficient for the automated
  checks, but a declared semantic or authority decision remains;
- `BLOCKED`: a required source, permission, validator, approval, or identity is
  unavailable or inconclusive;
- `UNSAFE`: a known active, failed, stale, newly observed, or otherwise
  unacceptable consumer remains.

The gate exits zero only for `READY_TO_RETIRE`.

Immediately before that result, the gate must also verify:

- the campaign store and required artifacts are available and intact;
- the manifest came from the expected repository commit or trusted execution
  context;
- the invocation is bound to the exact producer plan, source preconditions,
  trusted run identity, and current campaign writer;
- policy, configuration, validator, approval, and authorization digests still
  match the accepted evidence;
- target and replacement identities, schemas, and declared compatibility have
  not drifted;
- the reconciliation envelope remains fresh under the recorded clock policy;
- the stable DataHub publication still reads back the expected digests.

An unavailable check refuses. The producer workflow consumes the result in
the same trusted invocation and records that attempt. The campaign writer
durably issues at most one exact producer plan for a canonical manifest.
Execution requires byte-equivalent issued content, records intent before the
producer action, and consumes both the plan digest and campaign/manifest
binding even when the action outcome becomes unknown. Ordinary refusals do not
consume a plan. A prior zero exit, report, manifest, publication, or
independently recomputed plan is never a reusable authorization token.

## Campaign manifest

The canonical manifest includes:

- schema, campaign, specification, and policy versions;
- target and replacement identities;
- current campaign state and final decision;
- evidence envelope and snapshot digests;
- normalized consumers and receipt digests;
- blockers and review requirements;
- complete transition history;
- DataHub write/read-back reference;
- generation time and canonical manifest digest.

The manifest is deterministic except for explicitly supplied event times and
native identifiers. Rebuilding from the same event log must yield the same
digest.

Schema-version 1 manifests may omit `review_requirements` when none were
recorded so previously issued canonical digests remain stable. A newly
generated `REVIEW_REQUIRED` manifest carries each review code and plain
reason separately from blockers; presentation must not infer those reasons
from the decision label.

## Operator rendering

Every operator view validates the campaign-manifest schema and digest before
rendering. One shared presentation model supplies terminal inspect, terminal
explain, local HTML, and public HTML. It may translate stable codes into safe
recovery language, but it may not recompute a policy result or add UI-only
campaign state.

The first view includes target, replacement, exact decision, consumer and open
condition counts, bounded evidence coverage, required next action, and
manifest digest. Expanded views retain source mode, scope, freshness,
pagination, limitations, native action, receipt state, blocker or review
source, and canonical history. Unknown or empty coverage never renders as
complete, and a recorded receipt that is stale never renders as validated.

Public export is structural. Before rendering it replaces campaign, field,
consumer, source, principal, version, limitation, and event identities with
safe labels while retaining the decision, manifest digest, counts, coverage
state, and recovery shape. The original private manifest remains the
authority; the public view cannot be used as apply or gate authorization.

## Deployment lifecycle

The supported deployment is one versioned Python package, one local writer,
one path-bound SQLite store, and one product artifact directory. Deployment
preflight is a secret-safe claim about local readiness, not a substitute for
source preflight. It records only:

- package and Python versions;
- the selected `local`, `core-git-dbt`, or `data-quality-benchmark` profile;
- configuration reference names and presence, never their values;
- required local tool names and availability;
- digested store, artifact, and writer identities;
- schema versions and single-writer state;
- whether explicit local-only metrics are enabled;
- missing references or capabilities and exact next commands.

The built-in reference campaign is always fixture evidence and must remain
`BLOCKED` with `EVIDENCE_MODE_NOT_LIVE`. It proves a clean installation can
load packaged schemas and public data; it cannot satisfy a live policy.

The source archive is an explicit build input, not a snapshot of the
operational repository. It contains the runtime source, wheel-required fixture
data, schemas, package metadata, and stable deployment documentation. It must
exclude campaign state, raw or public acceptance evidence, status and goal
files, tests, and release scripts. Building that archive must reproduce the
release wheel byte-for-byte.

Removal is a two-step destructive protocol. A local ignored plan freezes the
exact store files and artifact-tree digests. Execution requires the operator
to pass that plan's exact digest, rejects target or writer mismatch, refuses
state drift and a held writer lock, and deletes only the named product store,
SQLite sidecars, lock, and artifact directory. Backups, configuration,
secret-provider values, and the Python package remain outside that action.
Package-manager removal is a separate explicit step.

Local operational metrics have no background collector and no remote export.
They run only when the operator invokes diagnostics; the environment opt-in
records whether a deployment intends to collect them.

## Stable refusal families

Initial refusal codes use these prefixes:

- `SPEC_`: invalid or unsupported intent;
- `AUTH_`: missing or insufficient authorization;
- `EVIDENCE_`: unavailable, partial, stale, or unverifiable evidence;
- `IDENTITY_`: missing, ambiguous, or inconsistent identity;
- `SOURCE_`: changed source or native precondition;
- `SCOPE_`: actual targets exceed the plan or allowlist;
- `APPLY_`: failed or partial mutation;
- `VALIDATION_`: failed or inconclusive native validation;
- `COMPENSATION_`: recovery unavailable or failed;
- `RECONCILIATION_`: graph refresh or comparison failure;
- `POLICY_`: consumer or campaign cannot transition;
- `INTEGRITY_`: digest, event, or artifact mismatch.
- `RUNTIME_`: trusted clock, local state, isolation, or execution boundary is
  unavailable;
- `GATE_`: final provenance, freshness, publication, or enforcement check
  failed.

Codes are machine-stable. Messages may improve without changing code meaning.
