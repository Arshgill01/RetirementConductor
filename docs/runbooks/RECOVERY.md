# Campaign recovery runbook

This runbook covers the supported single-writer SQLite deployment, database
backup and restore, schema roll-forward, partial adapter operations, and
operational diagnostics.

Use one Linux host, one resolved store path, one writer identity, and a local
filesystem. Do not place the active store on NFS, SMB, SSHFS, 9p, or another
shared state directory. A copied store is intentionally not authoritative at
a second path.

## Prepare the recovery context

Set non-secret local values. The writer identity and store path must match the
active deployment:

```bash
export RC_STORE=.retirement-conductor/campaigns.sqlite
export RC_WRITER=local-operator
export RC_BACKUP=.retirement-conductor/backups/campaigns-20260730T160000Z.sqlite
```

Stop other campaign commands before a manual restore. Normal backup and
diagnostic commands acquire the local campaign lock themselves.

## Create and inspect a backup

The destination must not exist. Use a current trusted RFC 3339 timestamp:

```bash
retirement-conductor campaign backup \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER" \
  --output "$RC_BACKUP" \
  --captured-at 2026-07-30T16:00:00Z
```

Inspect the JSON receipt. Require:

- `result` equal to `BACKUP_VERIFIED`;
- the expected schema versions;
- one entry for every campaign, with event count, event-stream digest, and
  canonical manifest digest;
- a canonical `logical_snapshot_digest`;
- a `database_digest`;
- a valid `backup_receipt_digest`.

The backup command holds the write lock, uses SQLite's online backup API,
checks SQLite integrity and foreign keys, replays every event stream, validates
cached manifests and gate ledgers, compares the live and backup logical
snapshots, writes atomically, refuses overwrite, and sets mode `0600`.

Verify the retained copy again while the live store is unchanged:

```bash
retirement-conductor campaign verify-backup \
  "$RC_BACKUP" \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER"
```

`BACKUP_MATCHES_LIVE_STATE` means exact logical equality at verification time.
It does not mean the backup is encrypted, remotely replicated, or current
after later events.

## Restore to the bound path

A backup can be restored only to the original resolved store path embedded in
its deployment binding. Opening it directly at the backup path or another
active path refuses as a copied store.

1. Stop every process using the campaign state directory.
2. Preserve the suspect database, WAL, and shared-memory files for incident
   review. Move them to an access-controlled incident directory; do not
   overwrite them.
3. Ensure the original store path is absent.
4. Install the verified backup at that exact original path with mode `0600`.
5. Open it with the same writer identity.
6. Inspect every affected campaign and compare its manifest digest with the
   backup receipt.
7. Run diagnostics and the repository acceptance suite before resuming
   mutation.

For a disposable local drill, after substituting explicit validated paths:

```bash
mv "$RC_STORE" .retirement-conductor/recovery/campaigns.suspect.sqlite
install -m 600 "$RC_BACKUP" "$RC_STORE"

retirement-conductor campaign inspect \
  --campaign ret-orders-legacy-status \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER"

retirement-conductor campaign diagnostics \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER" \
  --observed-at 2026-07-30T16:05:00Z \
  --stuck-after-seconds 3600
```

Do not run the example against an unverified path. Never delete the suspect
copy until the restored manifests, gate attempts, and native source state have
been inspected.

## Roll schema state forward

The runtime applies numbered SQLite migrations transactionally in order.
Before upgrading:

1. record the current application commit and `schema_versions`;
2. create and verify a backup;
3. stop the old writer;
4. install the reviewed application build;
5. open the exact store once with the same writer;
6. confirm all expected schema versions are present;
7. replay and inspect representative blocked, unsafe, review-required, and
   ready manifests;
8. create and verify a new post-migration backup.

The runtime refuses a database containing a schema version newer than it
understands. Downgrade is not supported. Restore the pre-upgrade binary and
backup together if roll-forward validation fails; never edit
`schema_migrations` manually.

## Recover partial operations

| Observed durable state | Required action | Forbidden shortcut |
|---|---|---|
| No new campaign event | retry with the same idempotency key after inspecting the refusal | inventing an event or new timestamp to bypass it |
| Event committed, cached manifest stale | reopen and replay; an intact cache prefix is repaired | editing cached manifest JSON |
| Apply intent `PENDING`, no known native response | reread exact native identity and before/after fingerprints | blind mutation retry |
| Apply intent `OUTCOME_UNKNOWN` | rerun the adapter recovery path, which rereads native state first | treating timeout as failure or success |
| Native state matches planned after state | record recovered apply, then run native validation | issuing a second native change |
| Native state matches neither before nor after | remain unsafe and escalate the intervening change | compensation or retry |
| Apply completed, validation absent or failed | rerun the native validator against the exact applied version | owner acknowledgment as validation |
| Compensation response lost | reread exact before/after fingerprints | a second compensation request |
| Compensation sees an owner edit | preserve it and remain `COMPENSATION_CONFLICT` | overwrite to force the old baseline |
| DataHub refresh or publication failed | retain local state, retry the bounded refresh/write, and require exact read-back | treating a write response as publication proof |
| Connector counters contradict stored aspects | inspect the exact stored schema and lineage aspects | accepting either counter as sole authority |
| Producer gate intent is `OUTCOME_UNKNOWN` | inspect the producer system; keep the issued plan consumed | replaying the gate plan |
| Event, cache, receipt, gate ledger, or backup integrity fails | stop mutation, preserve evidence, restore a verified backup if appropriate | recomputing digests to make content pass |
| Store reports writer or path mismatch | return to the declared original deployment | rebinding a copied store as authoritative |

Every recovery ends with source-native validation, fresh equivalent
reconciliation, policy evaluation, and a new producer plan if readiness still
holds.

## Diagnose operational state

Run:

```bash
retirement-conductor campaign diagnostics \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER" \
  --observed-at 2026-07-30T16:05:00Z \
  --stuck-after-seconds 3600
```

The output contains aggregate campaign, event, gate status, and refusal
counts; only campaign digests are used in alert identities. Investigate:

- every non-terminal campaign older than the deployment threshold;
- every stale, partial, unavailable, or unknown required source;
- any refusal code observed at least three times;
- every pending gate intent or unknown gate outcome;
- native identity claims whose owning campaign is not actively migrating.

An active identity claim is informational while its campaign is migrating.
It becomes suspicious when the campaign is stuck, blocked without an owner,
or no longer has a recovery plan.

## Retention and deletion

Backups contain confidential campaign evidence. Store them on encrypted,
access-controlled storage, keep only the verified generations required by
[the retention schedule](../../SECURITY.md), and do not upload them as public
artifacts.

Before deleting local evidence, stop the writer, confirm whether audit or
incident holds apply, and identify the exact store, `-wal`, `-shm`, lock,
backup, and ignored artifact paths. Ordinary file deletion does not guarantee
physical erasure on SSDs, snapshots, or copy-on-write storage. Use encrypted
volumes and approved key destruction when erasure assurance is required.

## Recovery drills

Run:

```bash
make test-recovery
make test-faults
make check
git diff --check
```

Inspect the recovery evidence for:

- deterministic logical snapshot regeneration;
- exact live and backup logical snapshot digests;
- restored canonical manifest and evidence references;
- copied-path and shared-filesystem refusals;
- tampered event and recomputed-cache refusal;
- interruption before and after durable writes;
- unknown mutation outcome reread without a second mutation;
- compensation conflict preserving an intervening edit;
- gate intent consumption after an unknown producer outcome.

The automated drill uses deterministic local fixtures. It proves the
credential-independent recovery contract, not live Looker service behavior.
