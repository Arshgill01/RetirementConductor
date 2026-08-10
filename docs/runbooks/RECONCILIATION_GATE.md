# Reconciliation and producer gate runbook

This runbook completes the disposable Git/dbt path through fresh DataHub
reconciliation, stable publication, and one manifest-bound producer action.
The reference producer action writes a public-safe local sentinel. It never
deletes a warehouse field or mutates production.

## Automated acceptance path

Start the disposable DataHub Core and MCP services, install the pinned dbt
tool, and keep the repository worktree clean:

```bash
make datahub-core-up
make git-dbt-tool
make test-end-to-end
make phase04-evidence
```

`make test-end-to-end` creates a unique ignored campaign, SQLite store, Git
repository, artifact tree, trusted run identity, and sentinel root. It then:

1. inventories one isolated DataHub consumer;
2. requires approval before one Git/dbt apply;
3. runs dbt parse, seed, build, and test in the sandbox;
4. refreshes and reconciles equivalent evidence;
5. publishes and verifies one stable DataHub summary;
6. prepares, freshly verifies, and executes one bounded producer action;
7. refuses replay and every drift, tamper, provenance, or availability probe;
8. introduces a second consumer and verifies that readiness reopens;
9. verifies that the 31-consumer rich graph remains `UNSAFE`; and
10. restores the isolated DataHub graph to its baseline.

Raw runtime evidence stays under `.retirement-conductor/e2e/phase04/`.
`make phase04-evidence` verifies its digests and ledger before deriving the
reviewable files under `artifacts/public/phase04/`.

## Manual command sequence

The preceding Git/dbt runbook must already have produced an accepted live
receipt. Set non-secret paths for one deployment writer:

```bash
export RC_CAMPAIGN=ret-orders-isolated
export RC_STORE=.retirement-conductor/campaigns.sqlite
export RC_WRITER=local-operator
export RC_ARTIFACTS=.retirement-conductor/artifacts
export RC_SENTINELS=.retirement-conductor/sentinels
```

After the relevant DataHub ingestion completes, reconcile against its signed
refresh receipt:

```bash
retirement-conductor campaign reconcile \
  --campaign "$RC_CAMPAIGN" \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER" \
  --artifact-dir "$RC_ARTIFACTS" \
  --refresh-receipt .retirement-conductor/datahub/seed-receipt.json \
  --indexing-timeout-seconds 30

retirement-conductor campaign publish \
  --campaign "$RC_CAMPAIGN" \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER" \
  --artifact-dir "$RC_ARTIFACTS"

retirement-conductor campaign verify-publication \
  --campaign "$RC_CAMPAIGN" \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER" \
  --artifact-dir "$RC_ARTIFACTS"
```

Inspect the comparison before continuing. Baseline and current scope digests
must match, refresh status must be `OBSERVED` within its timeout, required
sources must be live and complete, and added, disappeared, or invalidated
consumers must remain visible.

## Trusted producer invocation

The orchestrator supplies a non-secret trusted run identity and provider. The
writer identity, clean producer commit, marker digest, canonical manifest,
publication readback, evidence bindings, and action path are all checked in one
trusted invocation:

```bash
export RETIREMENT_CONDUCTOR_TRUSTED_CONTEXT=true
export RETIREMENT_CONDUCTOR_TRUSTED_RUN_ID=local-disposable-run
export RETIREMENT_CONDUCTOR_TRUST_PROVIDER=local-disposable-ci

retirement-conductor producer retire \
  --campaign "$RC_CAMPAIGN" \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER" \
  --artifact-dir "$RC_ARTIFACTS" \
  --producer-repository . \
  --producer-source-marker fixtures/producer/retire-order-status.json \
  --sentinel-root "$RC_SENTINELS" \
  --action sentinel
```

The command creates its five-minute plan binding internally, performs every
fresh source check, records intent before the action, and consumes the exact
manifest binding. Repeating the command must exit non-zero because the action
has already changed the producer state. Operators do not supply timestamps or
carry a separate lease in the default path.

`producer plan` and `gate` remain available for explicit recovery and legacy
handoff workflows. They are advanced compatibility commands, not the default
safety story.

## Required refusals

The gate must exit non-zero without another sentinel when any of these change
or become unavailable:

- campaign store or deployment writer;
- DataHub source or verified publication;
- producer commit, marker, trusted run, or trust context;
- consumer Git content or accepted native artifact;
- target or replacement identity and type;
- policy, validator configuration, authorization, or approval binding;
- plan content, expiry, issuance, or prior-consumption state; or
- canonical decision, including a newly observed consumer.

Do not repair a refusal by editing the plan or manifest. Refresh the relevant
source, reconcile the campaign, publish and verify the new canonical manifest,
then rerun the one-shot producer command only when policy permits it. Never
retry an `OUTCOME_UNKNOWN` PostgreSQL action; use `producer resolve-postgres`
to reread native state first.

## Final inspection

Run and inspect:

```bash
make test-end-to-end
make phase04-evidence
make check
git diff --check
```

Confirm that the ready and late manifests have different canonical digests,
both publications read back the exact reconciled digest under one stable
DataHub identity, the gate ledger contains one `EXECUTED` attempt, the sentinel
count is one, the late and rich paths are `UNSAFE`, and public/secret scans
pass.
