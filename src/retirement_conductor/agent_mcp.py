"""STDIO MCP server for a failure-closed Retirement Conductor agent."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from typing import Any

from retirement_conductor import __version__
from retirement_conductor.agent import AgentCommandRuntime, AgentSettings

SERVER_INSTRUCTIONS = (
    "Use DataHub MCP first to resolve the exact legacy and replacement fields and "
    "inspect graph context. Retirement Conductor remains authoritative for the "
    "campaign. Never treat empty evidence as absence. Never apply until the user "
    "reviews the exact plan and a human records authorization outside this server; "
    "pass the exact plan digest. After validation, reconcile, publish, and verify "
    "read-back. Never call the producer gate for a non-ready campaign. A refusal is "
    "a successful safety result and must not be bypassed."
)


def create_server(runtime: AgentCommandRuntime | None = None) -> Any:
    """Create the optional MCP server without burdening the core import path."""

    try:
        from mcp.server import MCPServer
        from mcp.types import ToolAnnotations
    except ModuleNotFoundError as exc:  # pragma: no cover - packaging boundary
        raise RuntimeError(
            "Install the agent extra with `pip install retirement-conductor[agent]` "
            "or run `uv sync --extra agent`."
        ) from exc

    tool_runtime = runtime or AgentCommandRuntime(AgentSettings.from_environment())
    server = MCPServer(
        name="retirement-conductor",
        title="Retirement Conductor",
        description=(
            "Verified change operations for replacing and retiring legacy data fields."
        ),
        instructions=SERVER_INSTRUCTIONS,
        version=__version__,
    )

    @server.tool(
        name="create_retirement_campaign",
        title="Create retirement campaign",
        description=(
            "Create durable local campaign state from a specification inside the "
            "configured specification root. This does not inspect or change sources."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
    )
    def create_retirement_campaign(
        specification: str,
        occurred_at: str,
    ) -> dict[str, Any]:
        return _campaign_result(
            tool_runtime.create_campaign(specification, occurred_at=occurred_at)
        )

    @server.tool(
        name="inspect_retirement_campaign",
        title="Inspect retirement campaign",
        description=(
            "Read the current canonical campaign view, including decision, evidence "
            "coverage, consumers, blockers, and next action."
        ),
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    def inspect_retirement_campaign(campaign_id: str) -> dict[str, Any]:
        result = tool_runtime.inspect_campaign(campaign_id)
        if _refused(result):
            return result
        return {
            "result": result["result"],
            "command_exit_code": result["command_exit_code"],
            "view": result["view"],
        }

    @server.tool(
        name="explain_retirement_campaign",
        title="Explain retirement campaign",
        description=(
            "Return the canonical plain-language explanation of the current decision "
            "and safe recovery actions."
        ),
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    def explain_retirement_campaign(campaign_id: str) -> dict[str, Any]:
        return tool_runtime.explain_campaign(campaign_id)

    @server.tool(
        name="inventory_retirement_consumers",
        title="Inventory retirement consumers",
        description=(
            "Resolve the exact field pair and record a bounded live DataHub inventory. "
            "The result is complete only inside its declared evidence envelope."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )
    def inventory_retirement_consumers(campaign_id: str) -> dict[str, Any]:
        result = tool_runtime.inventory_campaign(campaign_id)
        if _refused(result):
            return result
        snapshot = _mapping(result.get("snapshot"))
        return {
            "result": result["result"],
            "command_exit_code": result["command_exit_code"],
            "resolution": snapshot.get("resolution"),
            "consumers": snapshot.get("consumers"),
            "evidence_envelope": snapshot.get("evidence_envelope"),
            "snapshot_digest": snapshot.get("snapshot_digest"),
            "campaign": _manifest_summary(result.get("manifest")),
        }

    @server.tool(
        name="preflight_git_dbt_consumer",
        title="Preflight Git/dbt consumer",
        description=(
            "Join live DataHub evidence to one exact Git/dbt identity and record "
            "source fingerprints. This reads sources and cannot apply a change."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )
    def preflight_git_dbt_consumer(campaign_id: str) -> dict[str, Any]:
        result = tool_runtime.git_dbt_preflight(campaign_id)
        if _refused(result):
            return result
        preflight = _mapping(result.get("preflight"))
        return {
            "result": result["result"],
            "command_exit_code": result["command_exit_code"],
            "mapping": preflight.get("mapping"),
            "repository": preflight.get("repository"),
            "preflight_digest": preflight.get("preflight_digest"),
            "binding": result.get("binding"),
            "campaign": _manifest_summary(result.get("manifest")),
        }

    @server.tool(
        name="plan_git_dbt_migration",
        title="Plan Git/dbt migration",
        description=(
            "Produce the exact reviewable Git/dbt change plan and confirmation digest. "
            "Planning cannot mutate the repository."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )
    def plan_git_dbt_migration(campaign_id: str) -> dict[str, Any]:
        result = tool_runtime.git_dbt_plan(campaign_id)
        if _refused(result):
            return result
        return {
            "result": result["result"],
            "command_exit_code": result["command_exit_code"],
            "plan": result.get("plan"),
            "apply_confirmation": result.get("apply_confirmation"),
            "campaign": _manifest_summary(result.get("manifest")),
        }

    @server.tool(
        name="get_human_authorization_instructions",
        title="Get human authorization instructions",
        description=(
            "Return the exact out-of-agent command a human must run after reviewing "
            "the current plan. This tool cannot record or grant authorization."
        ),
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    def get_human_authorization_instructions(
        campaign_id: str,
        authorized_at: str,
        expires_at: str,
    ) -> dict[str, Any]:
        return tool_runtime.approval_instructions(
            campaign_id,
            authorized_at=authorized_at,
            expires_at=expires_at,
        )

    @server.tool(
        name="apply_git_dbt_migration",
        title="Apply Git/dbt migration",
        description=(
            "Apply only the authorized Git/dbt target after a human has separately "
            "recorded approval. Requires the exact current plan digest."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=True,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )
    def apply_git_dbt_migration(
        campaign_id: str,
        confirmed_plan_digest: str,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        result = tool_runtime.git_dbt_apply(
            campaign_id,
            confirmed_plan_digest=confirmed_plan_digest,
            occurred_at=occurred_at,
        )
        if _refused(result):
            return result
        apply = _mapping(result.get("apply"))
        return {
            "result": result["result"],
            "command_exit_code": result["command_exit_code"],
            "confirmed_plan_digest": result.get("confirmed_plan_digest"),
            "authorized_targets": result.get("authorized_targets"),
            "actual_targets": apply.get("actual_targets"),
            "before_fingerprint": apply.get("before_fingerprint"),
            "after_fingerprint": apply.get("after_fingerprint"),
            "apply_digest": apply.get("apply_digest"),
            "campaign": _manifest_summary(result.get("manifest")),
        }

    @server.tool(
        name="validate_git_dbt_migration",
        title="Validate Git/dbt migration",
        description=(
            "Run the declared native dbt validators and record a receipt. A source "
            "mutation or successful command alone is not validation."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    def validate_git_dbt_migration(
        campaign_id: str,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        result = tool_runtime.git_dbt_validate(campaign_id, expires_at=expires_at)
        if _refused(result):
            return result
        validation = _mapping(result.get("validation"))
        receipt = _mapping(result.get("receipt"))
        return {
            "result": result["result"],
            "command_exit_code": result["command_exit_code"],
            "validation_result": validation.get("result"),
            "validator": validation.get("validator"),
            "validation_digest": validation.get("validation_digest"),
            "receipt_id": receipt.get("receipt_id"),
            "receipt_digest": receipt.get("receipt_digest"),
            "terminal_disposition": receipt.get("terminal_disposition"),
            "campaign": _manifest_summary(result.get("manifest")),
        }

    @server.tool(
        name="reconcile_retirement_campaign",
        title="Reconcile retirement campaign",
        description=(
            "Reread native state and equivalent fresh DataHub evidence. New, stale, "
            "partial, or changed evidence can revoke prior readiness."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )
    def reconcile_retirement_campaign(campaign_id: str) -> dict[str, Any]:
        result = tool_runtime.reconcile_campaign(campaign_id)
        if _refused(result):
            return result
        return {
            "result": result.get("result"),
            "command_exit_code": result["command_exit_code"],
            "comparison": result.get("comparison"),
            "snapshot": result.get("snapshot"),
            "campaign": _manifest_summary(result.get("manifest")),
        }

    @server.tool(
        name="publish_retirement_summary",
        title="Publish retirement summary",
        description=(
            "Write one stable campaign summary to DataHub. The write response does not "
            "prove agent-visible publication; call verify_retirement_summary next."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )
    def publish_retirement_summary(campaign_id: str) -> dict[str, Any]:
        result = tool_runtime.publish_campaign(campaign_id)
        if _refused(result):
            return result
        return {
            "result": result["result"],
            "command_exit_code": result["command_exit_code"],
            "publication": result.get("publication"),
            "campaign": _manifest_summary(result.get("manifest")),
        }

    @server.tool(
        name="verify_retirement_summary",
        title="Verify retirement summary",
        description=(
            "Read the stable DataHub campaign summary back through the agent-visible "
            "surface and bind exact publication evidence."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )
    def verify_retirement_summary(campaign_id: str) -> dict[str, Any]:
        result = tool_runtime.verify_publication(campaign_id)
        if _refused(result):
            return result
        return {
            "result": result["result"],
            "command_exit_code": result["command_exit_code"],
            "publication": result.get("publication"),
            "campaign": _manifest_summary(result.get("manifest")),
        }

    @server.tool(
        name="prepare_producer_retirement_plan",
        title="Prepare producer retirement plan",
        description=(
            "Issue one short-lived producer plan for the exact current canonical "
            "manifest. This cannot make a non-ready campaign ready."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    def prepare_producer_retirement_plan(
        campaign_id: str,
        expires_at: str,
    ) -> dict[str, Any]:
        result = tool_runtime.prepare_producer_plan(campaign_id, expires_at=expires_at)
        if _refused(result):
            return result
        return result

    @server.tool(
        name="execute_retirement_gate",
        title="Execute retirement gate",
        description=(
            "Verify and consume the exact issued producer plan. This can execute the "
            "configured producer action only when every failure-closed check passes."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=True,
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )
    def execute_retirement_gate(
        campaign_id: str,
        plan: str | None = None,
    ) -> dict[str, Any]:
        return tool_runtime.execute_gate(campaign_id, plan=plan)

    return server


def _refused(result: Mapping[str, Any]) -> bool:
    return int(result.get("command_exit_code", 1)) != 0


def _campaign_result(result: dict[str, Any]) -> dict[str, Any]:
    if _refused(result):
        return result
    manifest = result.get("manifest")
    if manifest is None and "view" in result:
        return result
    return {
        "result": result.get("result", "OK"),
        "command_exit_code": result["command_exit_code"],
        "campaign": _manifest_summary(manifest),
    }


def _manifest_summary(value: object) -> dict[str, Any]:
    manifest = _mapping(value)
    campaign = _mapping(manifest.get("campaign"))
    consumers = [
        dict(consumer)
        for consumer in manifest.get("consumers", [])
        if isinstance(consumer, Mapping)
    ]
    closed = {"VALIDATED", "REMOVED", "NOT_APPLICABLE"}
    return {
        "id": campaign.get("id"),
        "name": campaign.get("name"),
        "state": manifest.get("state"),
        "decision": manifest.get("decision"),
        "manifest_digest": manifest.get("manifest_digest"),
        "consumer_count": len(consumers),
        "closed_consumer_count": sum(
            str(consumer.get("disposition")) in closed for consumer in consumers
        ),
        "consumers": consumers,
        "blockers": manifest.get("blockers", []),
        "review_requirements": manifest.get("review_requirements", []),
        "publication": manifest.get("publication"),
    }


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def main() -> None:
    """Run the local project-scoped STDIO server."""

    try:
        server = create_server()
    except RuntimeError as exc:  # pragma: no cover - packaging boundary
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    server.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
