"""No-secret access packet for the unresolved live Looker boundary."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import digest_bytes
from retirement_conductor.errors import Refusal
from retirement_conductor.looker import (
    DATAHUB_INGESTION_PERMISSIONS,
    REQUIRED_PERMISSIONS,
)
from retirement_conductor.vocabulary import RefusalCode

_CAMPAIGN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

LOOKER_ACCESS_VARIABLES = (
    "LOOKER_BASE_URL",
    "LOOKER_CLIENT_ID",
    "LOOKER_CLIENT_SECRET",
    "LOOKER_PLATFORM_INSTANCE",
    "LOOKER_PROJECT_ID",
    "LOOKER_MODEL_ID",
    "LOOKER_EXPLORE_ID",
    "LOOKER_FOLDER_ID",
    "LOOKER_FOLDER_PATH",
    "LOOKER_CONTENT_TARGET",
    "LOOKER_CONTENT_ID_PATTERN",
    "LOOKER_FOLDER_PATH_PATTERN",
    "LOOKER_LEGACY_REFERENCE",
    "LOOKER_REPLACEMENT_REFERENCE",
    "LOOKML_BASE_FOLDER",
    "LOOKER_WAREHOUSE_PLATFORM",
    "LOOKER_WAREHOUSE_INSTANCE",
    "LOOKER_WAREHOUSE_DATABASE",
    "LOOKER_WAREHOUSE_SCHEMA",
    "DATAHUB_GMS_URL",
)
DERIVED_EVIDENCE_VARIABLES = (
    "LOOKER_DATAHUB_URN",
    "LOOKER_GRAPH_SNAPSHOT_DIGEST",
)
OPTIONAL_SECRET_VARIABLES = ("DATAHUB_GMS_TOKEN",)
CONTROL_VARIABLES = (
    "LOOKER_MODE",
    "LOOKER_ALLOW_APPLY",
    "LOOKER_VERIFY_TLS",
)
ALIASES = {
    "LOOKER_BASE_URL": ("LOOKERSDK_BASE_URL",),
    "LOOKER_CLIENT_ID": ("LOOKERSDK_CLIENT_ID",),
    "LOOKER_CLIENT_SECRET": ("LOOKERSDK_CLIENT_SECRET",),
    "LOOKER_VERIFY_TLS": ("LOOKERSDK_VERIFY_SSL",),
}


def _configured(
    environment: Mapping[str, str],
    name: str,
) -> bool:
    names = (name, *ALIASES.get(name, ()))
    return any(environment.get(candidate, "").strip() for candidate in names)


def _variable_statuses(
    environment: Mapping[str, str],
    names: Sequence[str],
) -> list[dict[str, str]]:
    return [
        {
            "name": name,
            "status": "CONFIGURED" if _configured(environment, name) else "MISSING",
        }
        for name in names
    ]


def _status_table(statuses: Sequence[Mapping[str, str]]) -> str:
    rows = ["| Variable | Status |", "| --- | --- |"]
    rows.extend(f"| `{item['name']}` | {item['status']} |" for item in statuses)
    return "\n".join(rows)


def _permission_table(permissions: Sequence[str]) -> str:
    rows = ["| Permission | Effective state |", "| --- | --- |"]
    rows.extend(
        f"| `{permission}` | UNVERIFIED_UNTIL_PREFLIGHT |" for permission in permissions
    )
    return "\n".join(rows)


def build_looker_access_packet(
    *,
    campaign_id: str,
    environment: Mapping[str, str],
) -> tuple[str, dict[str, Any]]:
    """Build a packet containing names and statuses, never environment values."""

    if not _CAMPAIGN_ID.fullmatch(campaign_id):
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            "The access packet campaign ID must be shell-safe.",
        )
    access_statuses = _variable_statuses(environment, LOOKER_ACCESS_VARIABLES)
    derived_statuses = _variable_statuses(environment, DERIVED_EVIDENCE_VARIABLES)
    optional_statuses = _variable_statuses(environment, OPTIONAL_SECRET_VARIABLES)
    control_statuses = _variable_statuses(environment, CONTROL_VARIABLES)
    allow_apply_disabled = environment.get(
        "LOOKER_ALLOW_APPLY",
        "false",
    ).strip().lower() in {"", "false"}
    apply_state = "DISABLED" if allow_apply_disabled else "REQUIRES_DISABLE"
    required_permissions = sorted(REQUIRED_PERMISSIONS)
    ingestion_permissions = sorted(DATAHUB_INGESTION_PERMISSIONS)

    content = f"""# Retirement Conductor Looker access request

This packet preserves the credential-independent phase 06 resume point for
campaign `{campaign_id}`. It contains configuration names and status only.
Do not paste values into chat or a tracked file.

## Hard safety boundary

- `PROVISIONING_ALLOWED=false`
- Looker apply control: `{apply_state}`
- Do not create a Looker instance or any paid resource.
- Do not grant or elevate IAM roles.
- Do not raise BigQuery quotas, create tables, or run BigQuery queries.
- Store any supplied values only in the ignored `.env.local` file.
- Keep `LOOKER_ALLOW_APPLY` disabled through preflight, ingestion, and plan review.

## Direct configuration

{_status_table(access_statuses)}

## Evidence-derived configuration

These values must come from a fresh, fully paged DataHub inventory. Do not
predict either value from a display name.

{_status_table(derived_statuses)}

## Optional protected-DataHub secret

The local disposable DataHub Core does not require a token. A protected
DataHub boundary may require this ignored local value.

{_status_table(optional_statuses)}

## Safety controls

{_status_table(control_statuses)}

## Exact disposable object scope

- one pre-existing disposable Looker instance;
- one disposable LookML project, model, and Explore;
- one safe pre-existing warehouse connection named `retirement_fixture`;
- one isolated shared folder;
- exactly one saved Look identified as `look:<numeric-id>`;
- no production content, users, warehouse data, or wildcard mutation scope.

## Adapter permissions

The read-only preflight records the effective set safely and refuses if any
required adapter permission is absent.

{_permission_table(required_permissions)}

## DataHub ingestion permissions

These permissions may belong to a separate least-privileged ingestion
principal. Their effective state remains unverified until live preflight.

{_permission_table(ingestion_permissions)}

## Validate the recipe scaffolding

```bash
make phase06-recipes
```

## Run the scoped ingestion

After placing values in `.env.local`, export them locally without putting
secrets in command arguments. Run LookML ingestion before saved-Look
ingestion:

```bash
set -a
. ./.env.local
set +a
uv run --python 3.11 --with 'acryl-datahub[looker,lookml,datahub-rest]==1.6.0' \\
  datahub ingest -c deploy/datahub/recipes/looker-lookml.yml
uv run --python 3.11 --with 'acryl-datahub[looker,lookml,datahub-rest]==1.6.0' \\
  datahub ingest -c deploy/datahub/recipes/looker-saved-look.yml
```

Inspect the fresh DataHub result, then set only the exact observed
`LOOKER_DATAHUB_URN` and canonical `LOOKER_GRAPH_SNAPSHOT_DIGEST` in the
ignored file.

## Read-only configuration verification

```bash
retirement-conductor deployment preflight --profile looker-plan
```

This resume point does not assume a campaign already exists. It reports every
missing configuration reference without constructing a Looker client or
printing a value.

## Campaign bootstrap prerequisite

Adapter preflight requires a durable campaign specification that both
allowlists the exact `LOOKER_CONTENT_TARGET` and requires a Looker receipt.
That campaign cannot be created honestly until saved-Look ingestion resolves
the exact DataHub URN, fresh graph digest, and native target. Do not create a
placeholder campaign or guess those identities.

After the read-only deployment preflight and scoped ingestion, return control
to the active implementation run. It will inspect the live identities, write
an ignored exact specification, create campaign `{campaign_id}`, and only then
run adapter preflight.

## Post-bootstrap preflight and plan commands

```bash
retirement-conductor adapter looker preflight --campaign {campaign_id}
```

```bash
retirement-conductor adapter looker plan --campaign {campaign_id}
```

There is intentionally no apply command in this packet. Authentication does
not authorize mutation.

## Exact resume command

Resume at the first actionable read-only boundary:

```bash
retirement-conductor deployment preflight --profile looker-plan
```
"""
    summary: dict[str, Any] = {
        "result": "ACCESS_PACKET_WRITTEN",
        "campaign_id": campaign_id,
        "provisioning_allowed": False,
        "apply_control": apply_state,
        "resume_command": (
            "retirement-conductor deployment preflight --profile looker-plan"
        ),
        "campaign_state_required_before_adapter_preflight": True,
        "configuration": access_statuses,
        "derived_evidence": derived_statuses,
        "optional_secrets": optional_statuses,
        "controls": control_statuses,
        "adapter_permissions": [
            {"name": permission, "status": "UNVERIFIED"}
            for permission in required_permissions
        ],
        "ingestion_permissions": [
            {"name": permission, "status": "UNVERIFIED"}
            for permission in ingestion_permissions
        ],
    }
    return content, summary


def write_looker_access_packet(
    output: Path,
    *,
    campaign_id: str,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Atomically write the no-secret packet and return safe metadata."""

    values = os.environ if environment is None else environment
    content, summary = build_looker_access_packet(
        campaign_id=campaign_id,
        environment=values,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=output.parent,
        prefix=f".{output.name}.",
        delete=False,
    ) as temporary:
        temporary.write(content)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    try:
        temporary_path.chmod(0o600)
        os.replace(temporary_path, output)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return {
        **summary,
        "output": str(output),
        "packet_digest": digest_bytes(content.encode("utf-8")),
    }
