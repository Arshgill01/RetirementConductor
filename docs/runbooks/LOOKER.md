# Looker saved-Look runbook

This runbook joins one exact disposable saved Look to an existing campaign.
It does not authorize provisioning, production access, wildcard discovery, or
mutation merely because authentication succeeds.

## Current boundary

The dedicated zero-cost pretrial check has verified that no Looker instance
exists, trial and paid Looker quota remain unallocated, BigQuery query quota is
zero, and stored bytes are zero. That check is live GCP evidence only; it is
not live Looker adapter evidence.

`PROVISIONING_ALLOWED=false` remains controlling. Do not create a Looker
instance, grant IAM, change quota, create or query a BigQuery table, or
provision a paid resource. Phase 06 live acceptance waits for a user-approved
disposable instance or trial.

## Validate the credential-independent boundary

The saved-Look recipe uses the official DataHub `looker` source. The LookML
recipe parses a local project with an explicit connection mapping, avoiding an
admin API credential. Usage-history extraction is disabled because it queries
System Activity and is outside the zero-query boundary.

Validate both recipes with the pinned official DataHub 1.6.0 configuration
models and synthetic values:

```bash
make phase06-recipes
```

The public LookML fixture under `fixtures/looker-lookml-project/` is parsing
input only. It never connects to or queries a warehouse. The model and the
disposable live project must use the exact connection name
`retirement_fixture`: DataHub 1.6.0 expands environment references in values,
but not in `connection_to_platform_map` keys.

## Generate the no-secret access packet

This command works with all Looker variables absent and does not construct a
live client:

```bash
retirement-conductor adapter looker access-packet \
  --campaign <campaign-id>
```

Inspect
`.retirement-conductor/looker-access/access-request.md`. It lists only
configuration names and status, exact permission sets, one-object scope, a
read-only deployment verification command, post-bootstrap adapter commands,
and the preserved resume point. The resume command deliberately does not
assume a campaign already exists: its exact saved-Look allowlist and DataHub
identity cannot be frozen until live ingestion resolves them. Store values
only in ignored `.env.local`; never place secrets in command arguments,
tracked files, logs, reports, or chat.

## Ingest one exact disposable object

After the user supplies the approved boundary, populate the variables named in
the packet. Keep `LOOKER_ALLOW_APPLY=false`. Export the ignored file locally:

```bash
set -a
. ./.env.local
set +a
```

Run LookML before saved-content ingestion:

```bash
uv run --python 3.11 \
  --with 'acryl-datahub[looker,lookml,datahub-rest]==1.6.0' \
  datahub ingest -c deploy/datahub/recipes/looker-lookml.yml

uv run --python 3.11 \
  --with 'acryl-datahub[looker,lookml,datahub-rest]==1.6.0' \
  datahub ingest -c deploy/datahub/recipes/looker-saved-look.yml
```

The saved-content recipe excludes dashboards, uses one anchored numeric Look
ID and one anchored shared-folder path, runs one worker, emits column lineage,
and disables usage queries and embed URLs. Both recipes use a synchronous sink
so command completion waits for each DataHub write. DataHub 1.6.0 can still
emit contradictory source and sink counters, so inspect every ingestion
report and reread the resulting entity and lineage aspects. A zero-result
ingestion is not proof that the consumer is absent.

Resolve `LOOKER_DATAHUB_URN` from exact live search and set
`LOOKER_GRAPH_SNAPSHOT_DIGEST` only from the fresh fully paged campaign
inventory. Never predict either from a display name.

## Bootstrap, preflight, and plan

The first command after approved access is secret-safe deployment preflight:

```bash
retirement-conductor deployment preflight --profile looker-plan
```

It may initially report the two evidence-derived references as missing. After
ingestion resolves the exact saved-Look URN and a fresh inventory supplies its
graph digest, write an ignored campaign specification that:

- binds the exact target and replacement field identities;
- includes the exact `LOOKER_CONTENT_TARGET` in
  `authorization.allowed_native_objects`;
- requires a `looker` receipt;
- keeps authorization in plan mode.

Create the durable campaign from that reviewed specification. Never create a
placeholder campaign or guess the native target, DataHub URN, or graph digest.
Only then run adapter preflight and plan:

Preflight authenticates, records a digested principal identity and effective
permissions, checks model access, rereads the exact folder and saved Look,
binds immutable native identity to DataHub evidence, and refuses incomplete
pagination or expanded scope:

```bash
retirement-conductor adapter looker preflight \
  --campaign <campaign-id>

retirement-conductor adapter looker plan \
  --campaign <campaign-id>
```

With `LOOKER_ALLOW_APPLY=false`, preflight requires only the model-scoped read
permissions in [ACCESS.md](../ACCESS.md); `save_content` is neither required
nor treated as authority. Enabling apply requires both effective
`save_content` and the independent campaign controls below.

Inspect the permission, native baseline, inventory binding, and plan artifacts
under the ignored campaign artifact directory. The plan must target exactly
one `look:<numeric-id>` and change only the saved Look's `query_id`.

## Authorize, apply, and recover

Only after plan review may the operator set `LOOKER_ALLOW_APPLY=true` locally
and create a short-lived approval bound to the exact plan digest, source
version, target, and scope:

```bash
retirement-conductor adapter looker authorize \
  --campaign <campaign-id> \
  --principal <safe-principal-id> \
  --authorized-at <trusted-rfc3339-time> \
  --expires-at <trusted-rfc3339-time>

retirement-conductor adapter looker apply \
  --campaign <campaign-id> \
  --confirm-plan-digest <reviewed-plan-digest>
```

The workflow writes a durable intent before mutation. A timeout, cancellation,
or lost response remains `APPLY_OUTCOME_UNKNOWN` until a native reread proves
whether the exact planned state exists. Never blindly retry the mutation.
Read retries and status-specific refusal behavior are defined in the
[security model](../SECURITY_MODEL.md), and partial-state recovery is in the
[campaign recovery runbook](RECOVERY.md).

Compensation is separately approval-bound and refuses if any post-apply edit
changed the saved object:

```bash
retirement-conductor adapter looker compensate \
  --campaign <campaign-id>
```

After compensation, produce and approve a new plan before reapplying.

## Native validation and reconciliation

```bash
retirement-conductor adapter looker validate \
  --campaign <campaign-id>

retirement-conductor campaign reconcile \
  --campaign <campaign-id>

retirement-conductor campaign evaluate \
  --campaign <campaign-id>
```

Validation must include project/folder-scoped Content Validation and the
predeclared bounded query check. Fresh DataHub evidence must then state whether
the legacy edge disappeared, the replacement field edge appeared, or the
connector exposed only a weaker table-level limitation. Disappearance alone
does not close a consumer. Unrelated opaque consumers remain blocking.
