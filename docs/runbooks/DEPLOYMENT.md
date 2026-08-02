# Deployment runbook

This runbook installs and operates the supported Retirement Conductor runtime:
one released wheel, one Linux host, one writer identity, one path-bound SQLite
campaign store, and one local artifact directory.

There is no supported Retirement Conductor container or multi-writer service.
DataHub Core may run in containers, but the product remains a host-installed
command because Git worktrees, dbt, the SQLite store, and the validator
isolation boundary all have explicit host-side ownership.

## Verify the release

Build the repository release only from a clean, reviewed commit:

```bash
make package

export RC_RELEASE=.retirement-conductor/phase08/release/dist
cd "$RC_RELEASE"
sha256sum --check SHA256SUMS
```

The directory contains:

- one `retirement_conductor-<version>-py3-none-any.whl`;
- one minimal source archive;
- `runtime-requirements.txt`, with hashes for every runtime dependency;
- a CycloneDX 1.5 runtime SBOM;
- `SHA256SUMS`;
- ignored raw package evidence.

Inspect the filename and checksum instead of selecting an unbounded wildcard in
automation. The current release is reproducible byte-for-byte on the observed
build host, but it is not cryptographically signed. A checksum detects changed
bytes; it does not establish who published them.

## Install on one Linux host

Python 3.11 through 3.14 are the executed compatibility boundary. Create a
dedicated environment and install dependencies from the hash-locked file
before installing the wheel without dependency resolution:

```bash
export RC_RELEASE=/reviewed/path/to/release/dist
export RC_VENV=/opt/retirement-conductor/venv
export RC_WHEEL=/reviewed/path/to/retirement_conductor-0.2.0-py3-none-any.whl

uv venv --python 3.11 "$RC_VENV"
uv pip install \
  --python "$RC_VENV/bin/python" \
  --require-hashes \
  --no-config \
  -r "$RC_RELEASE/runtime-requirements.txt"
uv pip install \
  --python "$RC_VENV/bin/python" \
  --no-deps \
  --no-config \
  "$RC_WHEEL"

"$RC_VENV/bin/retirement-conductor" --version
```

The wheel contains the campaign schemas, migrations, and public-safe built-in
reference data. Do not add the source checkout to `PYTHONPATH`; acceptance
executes the installed console entry point from outside the repository.

## Configure state and integrations

Copy [`.env.example`](../../.env.example) to an ignored, mode-`0600` local
configuration file or populate the same names through the deployment's secret
provider. Never place a token, secret, private query, or credential value in a
command argument, tracked file, diagnostic artifact, or support request.

At minimum, bind the local deployment:

```bash
export RETIREMENT_CONDUCTOR_STORE=/var/lib/retirement-conductor/campaigns.sqlite
export RETIREMENT_CONDUCTOR_WRITER_ID=retirement-conductor-primary
export RETIREMENT_CONDUCTOR_ARTIFACT_DIR=/var/lib/retirement-conductor/artifacts
export RETIREMENT_CONDUCTOR_LOCAL_METRICS=false
```

The store and artifact directory must be separate product-owned targets on a
local filesystem. Use the same resolved store path and writer ID on every
invocation. NFS, SMB, SSHFS, 9p, a copied store path, or a second writer is
unsupported and must refuse.

For the Core Git/dbt path, also provide the named DataHub and Git/dbt
references from `.env.example`. `DATAHUB_GMS_TOKEN_REFERENCE` names the secret
reference; its value is not a substitute for the token supplied by the secret
provider. Keep apply flags false until an exact plan has been inspected and
authorized.

## Run deployment and source preflights

First inspect the local deployment boundary:

```bash
retirement-conductor deployment preflight \
  --profile core-git-dbt \
  --store "$RETIREMENT_CONDUCTOR_STORE" \
  --writer-id "$RETIREMENT_CONDUCTOR_WRITER_ID" \
  --artifact-dir "$RETIREMENT_CONDUCTOR_ARTIFACT_DIR"
```

Profiles have narrow meanings:

| Profile | What it checks |
|---|---|
| `local` | Python, state path, writer binding, artifact path, and metrics setting |
| `core-git-dbt` | local checks plus named DataHub/Git/dbt references and required host tools |
| `data-quality-benchmark` | Core/Git/dbt checks plus the pinned dataset registry, ignored cache, generator, and oracle references |

A ready deployment preflight proves only local configuration presence, tool
availability, and state ownership. It does not prove remote authentication,
permissions, source freshness, or a working validator. Run the native
preflights next:

```bash
retirement-conductor datahub preflight
retirement-conductor adapter git-dbt preflight \
  --campaign <campaign-id> \
  --store "$RETIREMENT_CONDUCTOR_STORE" \
  --writer-id "$RETIREMENT_CONDUCTOR_WRITER_ID" \
  --artifact-dir "$RETIREMENT_CONDUCTOR_ARTIFACT_DIR"
```

DataHub Cloud is an optional integration boundary, not a prerequisite for the
Core-supported path; never infer Cloud behavior from Core results. Looker is
not a supported deployment profile.

## Evaluate the installed package safely

The built-in reference checks package data and deterministic policy without
external systems:

```bash
retirement-conductor reference run \
  --output-dir .retirement-conductor/reference
```

Its evidence mode is `fixture`, and its expected decision is `BLOCKED` with
`EVIDENCE_MODE_NOT_LIVE`. A positive fixture must never authorize retirement.

Repository maintainers can exercise the installed wheel against disposable
live DataHub Core, Git, dbt, and the producer sentinel with:

```bash
make test-reference-campaign
```

That command is destructive only to repository-owned disposable resources. It
is not a production runbook. Inspect the generated decisions, native
validation receipt, publication read-back attempts, late-consumer refusal,
rich-graph refusal, package identity, and sentinel count.

## Local opt-in diagnostics

There is no background collector and no remote metrics export. Setting
`RETIREMENT_CONDUCTOR_LOCAL_METRICS=true` records an operator opt-in in
preflight; it does not start collection. Diagnostics run only on explicit
invocation:

```bash
retirement-conductor campaign diagnostics \
  --store "$RETIREMENT_CONDUCTOR_STORE" \
  --writer-id "$RETIREMENT_CONDUCTOR_WRITER_ID" \
  --observed-at 2026-07-30T16:05:00Z \
  --stuck-after-seconds 3600
```

Retain the redacted aggregate locally under the deployment's evidence policy.
It contains digested campaign identities, not raw source content. Keep the
opt-in false if the deployment will not retain those local observations.

## Back up, upgrade, and roll back

Follow the [recovery runbook](RECOVERY.md) before changing the package:

1. stop other campaign commands;
2. create and verify an online backup;
3. retain the old wheel, runtime lock, and backup as one rollback set;
4. install the new hash-verified release;
5. open the original store with the same writer;
6. inspect schema versions and representative campaigns;
7. run diagnostics and native preflights;
8. create a verified post-upgrade backup.

Do not downgrade a migrated database in place. If roll-forward validation
fails, restore the verified pre-upgrade database at its original bound path
and reinstall the matching prior wheel.

Maintainers rehearse this behavior with:

```bash
make test-upgrade
make test-recovery
```

## Remove state and uninstall

State removal and package uninstall are intentionally separate. Stop all
runners, retain a verified backup if recovery may be needed, and generate one
ignored plan:

```bash
retirement-conductor deployment removal-plan \
  --output .retirement-conductor/removal-plan.json \
  --generated-at 2026-07-30T17:00:00Z \
  --store "$RETIREMENT_CONDUCTOR_STORE" \
  --writer-id "$RETIREMENT_CONDUCTOR_WRITER_ID" \
  --artifact-dir "$RETIREMENT_CONDUCTOR_ARTIFACT_DIR"
```

Inspect its exact targets, exclusions, file digests, and
`removal_plan_digest`. Execute only the unchanged plan:

```bash
retirement-conductor deployment remove-state \
  --plan .retirement-conductor/removal-plan.json \
  --confirm-plan-digest <exact-removal-plan-digest> \
  --store "$RETIREMENT_CONDUCTOR_STORE" \
  --writer-id "$RETIREMENT_CONDUCTOR_WRITER_ID" \
  --artifact-dir "$RETIREMENT_CONDUCTOR_ARTIFACT_DIR"
```

Without exact confirmation, on target drift, or while the writer lock is held,
the command refuses. It removes only the bound active store, SQLite sidecars,
lock, and artifact directory. It does not remove retained backups,
configuration, secret-provider values, the confirmation plan, or the Python
package.

After inspecting the removal receipt, uninstall the package explicitly:

```bash
uv pip uninstall \
  --python "$RC_VENV/bin/python" \
  retirement-conductor
```

Ordinary deletion does not guarantee physical erasure from snapshots or
copy-on-write storage. Follow the security retention and key-destruction
policy where erasure assurance is required.

## CI and automation boundary

CI may invoke the same installed CLI, but one job must own the state path and
writer identity. Never fan out commands over copies of one SQLite store.
Pass plan digests and non-secret object identities as artifacts; supply
credentials through the CI secret provider. Apply and producer actions remain
explicit, allowlisted, and immediately preceded by fresh preconditions.

Executed platform and integration boundaries are listed in
[the compatibility matrix](../COMPATIBILITY.md). Independent evaluation uses
[the evaluation guide](../EVALUATION.md).
