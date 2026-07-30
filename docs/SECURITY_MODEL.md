# Security model

This model defines the supported security boundary for the command-line,
single-writer deployment. It covers the current Git/dbt adapter, the
deterministic Looker adapter contract, DataHub inventory and publication, the
SQLite campaign store, generated artifacts, and the producer gate.

It does not turn fixture evidence into live acceptance. The Looker API,
native validation, and refreshed saved-content ingestion remain unverified
against a live disposable Looker instance.

## Security objectives

Retirement Conductor must fail closed when it cannot prove all of these
properties:

- evidence belongs to the exact campaign, source, scope, and observed version;
- an approved mutation targets only the exact reviewed native object;
- the native source still matches its approved precondition;
- validation ran in the source system or supported isolated native tool;
- accepted receipts and campaign events retain their canonical bindings;
- reconciliation is fresh, complete within its declared envelope, and
  equivalent to the baseline scope;
- the producer action runs only in the exact trusted invocation that consumed
  its short-lived plan;
- credentials and unrestricted source content do not enter retained or public
  evidence.

An empty result, successful HTTP status, digest, owner acknowledgment, model
instruction, or previously green report cannot satisfy these objectives by
itself.

## Assets and classification

| Asset | Classification | Authority | Retained form |
|---|---|---|---|
| API tokens, client secrets, cookies, private keys | secret | deployment secret provider | never retained by the product |
| Producer retirement credential | secret and destructive | producer workflow | never available to the campaign process |
| Warehouse query text and result rows | restricted source data | warehouse or BI source | bounded digest, counts, and redacted summary only |
| Private repository and Looker content | restricted source data | Git or Looker | exact fingerprints, safe identities, and redacted evidence |
| Approvals, plans, events, receipts, gate attempts | confidential audit state | campaign writer plus native sources | protected SQLite store and verified backups |
| Raw redacted adapter evidence | confidential operational evidence | source response plus adapter | ignored local artifact directory |
| Canonical manifest | confidential operational evidence | event replay and deterministic policy | SQLite, private export, digested publication summary |
| Public report and tracked acceptance artifacts | public-safe | structural redaction and repository review | tracked repository |

The retention and deletion schedule is in [SECURITY.md](../SECURITY.md).

## Actors and trust assumptions

- The operator may declare scope and approve a reviewed plan, but an approval
  cannot change deterministic policy or native preconditions.
- The campaign writer is trusted to operate one local state directory. It is
  not trusted with the producer's destructive credential.
- DataHub, Git, dbt, Looker, repositories, API payloads, model output, and
  source owners can be stale, compromised, malformed, or misleading.
- The producer workflow is trusted only inside its attested invocation and
  only for the exact short-lived plan it consumes.
- A host administrator can read process memory and local files. Host hardening,
  disk encryption, identity management, and backup custody remain deployment
  responsibilities.
- SHA-256 digests identify content and detect change. They do not establish who
  produced the content.

## Trust boundaries

```text
secret provider
    │ runtime-only credentials
    ▼
adapter process ─── untrusted API / repository / validator input
    │                    │
    │ redacted claims    │ native source remains authoritative
    ▼                    ▼
single-writer SQLite ── deterministic policy
    │                    │
    │ bounded summary    │ one-time issued plan
    ▼                    ▼
DataHub publication   separately privileged producer gate
    │
    ▼
structurally redacted public artifacts
```

Crossing a boundary requires an exact identity, explicit capability, fresh
precondition, canonical digest, and source-specific validation. Free-form
content never crosses as authority.

## Capability and least-privilege matrix

| Principal | Permitted capability | Explicitly excluded |
|---|---|---|
| Campaign core | local event, manifest, receipt, and policy operations | producer schema mutation and wildcard native access |
| DataHub inventory reader | exact search, schemas, ownership, lineage, paths, permitted query context | lifecycle mutation and unrestricted metadata writes |
| DataHub campaign publisher | update and reread one stable campaign summary | transaction-state authority and target deprecation |
| Git/dbt planner | read one declared repository and produce a bounded plan | branch or file mutation |
| Git/dbt applier | one approved branch and allowlisted file set | default-branch rewrite, hooks, unrelated paths, warehouse production access |
| dbt validator | copied project, pinned tool, local disposable target | network, host home, source checkout, secrets, external packages |
| Looker planner and validator | model-scoped reads using `access_data`, `explore`, `see_lookml`, `see_looks`, `see_queries`, `see_schedules`, and `see_users` | saved-content mutation |
| Looker applier | planner permissions plus `save_content`, exact model, folder, and one saved Look | admin role, wildcard folder writes, dashboards, merged results |
| Looker ingestion | separately scoped official connector permissions in [ACCESS.md](ACCESS.md) | adapter apply authority |
| Producer gate | verify and consume one exact plan in trusted producer CI | general campaign mutation and reusable readiness tokens |
| Backup operator | read one store and create a mode-`0600` non-overwriting backup | alternate-path authority, network-shared active state, silent overwrite |

Authentication alone grants no campaign authority. Git/dbt additionally
requires specification mode `apply`, adapter opt-in, a durable approval, and
exact plan confirmation. Looker requires adapter opt-in, effective
`save_content`, a durable approval, and exact plan confirmation. The producer
credential is never shared with either adapter.

## Authorization binding

Mutation authorization is bound to:

- campaign identifier;
- exact plan digest;
- source version and before fingerprint;
- exact native identity and approved target set;
- principal and required capability;
- authorization configuration digest;
- trusted authorization and expiry times.

The native identity claim prevents two active campaigns from mutating the
same object. A recreated object, changed target membership, changed
replacement, expired approval, policy drift, validator drift, or source drift
invalidates the prior authority. Plan-only mode is evaluated before any
native write.

## Abuse cases and controls

| Abuse or failure | Deterministic control | Safe result |
|---|---|---|
| Specification requests another file or Look | schema, allowlist, identity, and target-set equality | scope refusal before mutation |
| Source text instructs the model or operator to bypass policy | source content remains data; policy and command scope do not parse instructions | instruction omitted or redacted; no new authority |
| Read credential is mistaken for apply authority | separate opt-in and effective capability checks | `AUTH_APPLY_DISABLED` or permission refusal |
| Approval is replayed for another source or target | exact campaign, plan, source, target, scope, and expiry binding | authorization refusal |
| API returns 401, 403, 404, 409, or 422 | status-specific redacted refusal | denied, missing, conflicted, or invalid state remains visible |
| API returns 429 or transient 5xx on a read | bounded backoff and retry | success or unavailable evidence; never false readiness |
| Mutation times out, loses connection, or returns ambiguous 5xx | no automatic mutation retry; durable unknown state and native reread | `APPLY_OUTCOME_UNKNOWN` |
| Owner edits after apply | exact post-apply fingerprint before compensation | `COMPENSATION_CONFLICT`; owner edit preserved |
| Event, receipt, plan, cache, or backup changes | schema, canonical digest, column binding, replay, and SQLite checks | integrity refusal |
| Cache update is interrupted after event commit | event stream remains authoritative; intact cache prefix may be repaired | replayed state |
| Store is copied to another path | deployment path binding checked read-only before journal mutation | writer mismatch refusal |
| Store is placed on a known shared filesystem | mount-type preflight | writer mismatch refusal |
| Two campaigns claim one native identity | transactional active identity claim | overlap refusal |
| Repository attempts path, symlink, hook, dependency, process, secret, or network escape | copied bubblewrap boundary and explicit allowlists | scope or sandbox refusal |
| DataHub reports no consumers | completeness, pagination, permissions, freshness, and source status remain required | missing or incomplete evidence blocks |
| Connector counters contradict stored metadata | direct exact aspect reread is authoritative | contradiction retained as a limitation |
| Gate plan is delayed, replayed, recomputed, or used in another CI run | trusted run binding, expiry, durable issuance, and single consumption | gate refusal |
| Gate action response is lost | intent remains consumed and outcome unknown | no automatic replay |

## HTTP failure contract

Reads retry only 408, 425, 429, 500, 502, 503, 504, connection loss,
timeout, or malformed JSON, up to the configured bound. `Retry-After` is
capped at two seconds; other retries use deterministic capped backoff.

Mutations execute once. A timeout, connection loss, malformed response, 408,
425, or 5xx response is outcome unknown. A 401/403 is permission denial, 404
is exact-identity loss, 409 requires native reread and replanning, and 422 is
native validation failure. Refusals retain method, bounded path, status,
error type, and retry count only; they do not retain response bodies, query
parameters, credentials, or native content.

## Store and recovery boundary

The active SQLite file is bound to a digest of its resolved deployment path
and writer identity, uses WAL with full synchronization, and is mode `0600`.
Writes take a non-blocking local file lock. Known network and shared
filesystem types refuse. This establishes one supported local writer; it does
not provide distributed consensus.

Backups are SQLite online backups made while holding the campaign write lock.
Before publication they pass SQLite integrity and foreign-key checks, exact
event replay, manifest comparison, gate-ledger validation, native-claim
validation, and a logical snapshot comparison with the live store. They are
written atomically, never overwrite a destination, and are mode `0600`.

See the [recovery runbook](runbooks/RECOVERY.md) for restore, migration, and
partial-state drills.

## Operational signals

`campaign diagnostics` emits only aggregate counts and digested campaign
identities. The alert contract includes:

- non-terminal campaigns older than the configured threshold;
- required sources recorded as stale, partial, unavailable, or unknown;
- refusal codes repeated at least three times;
- unresolved producer gate outcomes;
- pending producer gate intents;
- active native identity claims.

Diagnostics first validate the logical store. A corrupted ledger refuses
instead of reporting health.

## Residual boundaries

- A malicious host administrator is outside the application boundary.
- Backups are permission-protected but not encrypted by the application.
- File deletion cannot promise physical erasure on snapshots, SSDs, or
  copy-on-write filesystems.
- Known shared filesystem types refuse, but this is not distributed
  split-brain prevention for every possible custom filesystem.
- Automated retention enforcement is not yet implemented; the operator
  follows the documented schedule.
- Live Looker permission behavior, retries, recovery, and validation remain
  pending until the approved disposable boundary exists.
- A real producer integration must enforce the gate in the producer workflow;
  the disposable sentinel proves the binding and refusal mechanics, not
  production warehouse privilege.
