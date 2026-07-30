# Security

Retirement Conductor is designed to inspect and eventually change downstream
consumer systems. Until a deployment has passed the security and reliability
phase, use only disposable environments and data. The detailed assets,
actors, trust boundaries, abuse cases, and capability matrix are in the
[security model](docs/SECURITY_MODEL.md).

## Supported development boundary

- Read and plan are the default capabilities.
- Apply requires explicit, target-bound authorization.
- The general campaign process must not hold credentials for destructive
  producer actions.
- Native operations must use documented public interfaces.
- Development and tests must not target production systems.

## Sensitive material

Never commit or include in public artifacts:

- DataHub, Git provider, warehouse, or BI credentials;
- cookies, access tokens, API client secrets, private keys, or session data;
- unrestricted query text or query results;
- private repository content;
- personal or sensitive data;
- raw responses that reveal internal infrastructure or principals.

Use ignored environment files or a deployment secret provider. Logs and
reports must record safe identifiers and redacted summaries.

## Artifact classification and retention

Retention is bounded by both minimization and the need to explain a producer
decision. An operator may shorten a maximum below, but may not delete the only
evidence supporting an active campaign or completed producer action.

| Material | Retention rule |
|---|---|
| Credentials, tokens, cookies, private keys | process memory only; never write to artifacts, logs, reports, or backups |
| Unrestricted SQL, query rows, private content, raw API bodies | do not retain; reduce to approved redacted claims, counts, fingerprints, and bounded diagnostics |
| Ignored redacted raw evidence | delete after promotion to normalized claims and acceptance inspection; 30 days is the maximum without an incident hold |
| Active campaign SQLite store | retain while any campaign can resume or any gate outcome is unresolved |
| Terminal campaign store and accepted receipts | retain for 90 days after the producer action by default, or the longer period required by the deployment's audit policy |
| Verified store backups | keep the newest verified generation and one prior generation while active; delete superseded generations within 7 days; after closure follow the store's 90-day rule |
| Safe operational logs | 14 days maximum unless an incident hold applies |
| Structurally redacted public artifacts | may remain in repository history after secret and public-artifact review |

Retention enforcement is currently an operator runbook responsibility, not an
automated product claim. A deployment must record any different legal or audit
period before live use.

Before deletion, stop the writer and resolve the exact ignored artifact,
database, WAL, shared-memory, lock, and backup paths. Do not use a broad
recursive target. Ordinary file deletion does not guarantee physical erasure
from SSDs, filesystem snapshots, remote copies, or copy-on-write storage.
Deploy on encrypted storage and use approved key destruction when erasure
assurance is required.

## Local state and backup protection

- The active campaign database and local lock are forced to mode `0600`.
- One writer identity and one resolved local path are bound into the store.
- A copied store at another path and known shared filesystems refuse.
- A backup never overwrites an existing destination, is written atomically at
  mode `0600`, and must reproduce the live logical campaign state.
- Backups contain confidential audit evidence but are not encrypted by the
  application. Protect them with deployment encryption and access controls.
- Restore, migration, partial-state, and deletion procedures are in the
  [recovery runbook](docs/runbooks/RECOVERY.md).

## Reporting a vulnerability

Use GitHub's private vulnerability reporting for this repository. Include:

- affected version or commit;
- component and capability involved;
- safe reproduction steps;
- potential source, evidence, or credential exposure;
- whether mutation or false readiness is possible;
- suggested containment if known.

Do not open a public issue containing an exploitable sequence, credential, or
sensitive artifact.

## Security properties

The product is expected to preserve:

- no mutation from read-only or plan-only authority;
- exact source and target preconditions before apply;
- no readiness from partial, stale, ambiguous, or tampered evidence;
- no silent success after partial mutation;
- no blind retry after a mutation whose outcome is unknown;
- no compensation that overwrites an intervening native change;
- isolated execution of untrusted repositories, dbt code, macros, and hooks;
- clear separation between integrity digests and trusted provenance;
- one authoritative campaign writer for the SQLite deployment;
- no reusable gate success outside its exact trusted producer invocation;
- resumable safe state after interruption;
- minimum required evidence retention;
- stable audit history for policy decisions.

See [Risk register](docs/RISKS.md) and
[Security and reliability phase](docs/phases/07-security-reliability.md).
