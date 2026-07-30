# Maintenance and release policy

Retirement Conductor is a pre-1.0 package. Package versions follow semantic
versioning, while campaign manifests, records, evidence packets, receipts, and
the SQLite schema retain their own explicit versions. A package version change
does not silently change a stored contract's meaning.

## Compatibility changes

- Patch releases fix behavior without changing a public contract.
- Minor releases may add compatible behavior and numbered roll-forward
  migrations.
- Any incompatible contract change requires a new schema version, migration
  behavior, refusal and replay coverage, a decision entry, and operator
  documentation.
- A database containing a schema version newer than the runtime understands
  refuses. In-place downgrade is unsupported.
- The executed [compatibility matrix](COMPATIBILITY.md), not a dependency
  version range alone, defines verified support.

## Release checklist

Release only from a clean, reviewed commit:

```bash
uv lock --check
make check
make package
make test-install
make test-upgrade
make test-reference-campaign
git diff --check
```

Inspect rather than merely accept exit status:

- wheel metadata, console entry point, schemas, migrations, and reference data;
- minimal source-archive membership and unsafe member types;
- byte-for-byte rebuild results;
- hash-locked runtime requirements, SBOM, and checksums;
- clean-install logs across the executed Python matrix;
- missing-configuration and copied-state refusals;
- upgrade, backup, rollback, confirmed removal, and uninstall evidence;
- live Core reference decisions, native dbt receipt, publication read-back,
  late-consumer refusal, rich-graph refusal, and producer sentinel count;
- public artifact and secret scans;
- status, ledger, risks, decisions, documentation, and package version.

The source archive deliberately excludes runtime state, raw evidence, tracked
acceptance artifacts, status files, tests, and release scripts. This prevents
the artifact from recursively containing or changing with the evidence that
describes it. It remains sufficient to build the wheel and includes the
public-safe runtime data and deployment documentation.

Every release note must name:

- package and schema versions;
- behavior and refusal changes;
- migrations and rollback pair;
- executed compatibility boundary;
- security and dependency changes;
- live, fixture, replay, and analysis evidence separately;
- unresolved integrations, signing limitations, and operator boundaries.

There is no automated registry publication, tag creation, release signing, or
attestation service yet. `make package` creates a local reviewed release
directory; it does not publish or establish authorship. Add those mechanisms
only with an operator-owned identity, key lifecycle, and release destination.

## Backup and rollback

Before an upgrade, retain the verified old wheel, its runtime lock, and a
verified pre-upgrade database backup as one rollback set. Validate the new
runtime at the original store path with the same writer. If validation fails,
restore the prior database and package together. Follow the
[recovery runbook](runbooks/RECOVERY.md); never edit migration rows or attempt
an in-place downgrade.

## Dependency and security maintenance

At each release and at least monthly while actively evaluated:

- update the lock only through an intentional reviewed change;
- run the repository vulnerability, license, secret, and public-artifact
  scans;
- review runtime and development dependency advisories;
- re-run native integration checks when a pinned source version changes;
- confirm credential, retention, backup, and deletion documentation;
- document any accepted vulnerability or license exception with owner,
  expiry, and scope.

Never broaden credentials, enable a paid service, or mutate production
infrastructure as part of routine dependency maintenance.

## Contributions and support

Use the issue tracker for public-safe defects and proposals. Security reports
follow [SECURITY.md](../SECURITY.md). Changes follow
[CONTRIBUTING.md](../CONTRIBUTING.md) and require successful and refusal
coverage, inspected evidence, and an explicit evidence mode.

Support statements must name the package version, exact source version,
evidence mode, refusal code, and remaining limitation. Do not request tokens,
private queries, raw campaign databases, or sensitive artifacts in issues or
chat. A new adapter or deployment shape is accepted only after an observed
requirement demonstrates value beyond the current bounded runtime.
