# Source ledger

Technical and competitive claims use primary public sources. Source
capabilities can change; review this ledger before changing product
positioning or integration contracts.

Checked: 2026-07-30.

## DataHub

| Source | Revision or version | Used for |
|---|---|---|
| [DataHub Core](https://github.com/datahub-project/datahub) | `2bbb932452e39eb8680489b79071ff7aa1de540e` | metadata model, deprecation mutation, GraphQL behavior |
| [DataHub documentation](https://docs.datahub.com/docs/) | `1.6.0` site | lineage, MCP, contracts, incidents, applications, workflows |
| [DataHub MCP Server](https://github.com/acryldata/mcp-server-datahub) | `9a6946daa7d30eb481c82dd8ee5e15ae6526a3c9` | actual open-source tool registry and lineage behavior |
| [DataHub Skills](https://github.com/datahub-project/datahub-skills) | `f22f93074cf265ba6f9401947404f090c2584d9d` | shipped search, lineage, and enrichment workflows |

Key pages:

- [DataHub MCP Server](https://docs.datahub.com/docs/features/feature-guides/mcp/)
- [DataHub lineage](https://docs.datahub.com/docs/features/feature-guides/lineage/)
- [Data contracts](https://docs.datahub.com/docs/managed-datahub/observe/data-contract)
- [Incidents](https://docs.datahub.com/docs/incidents/incidents)
- [Change proposals](https://docs.datahub.com/docs/managed-datahub/change-proposals)
- [DataHub applications](https://docs.datahub.com/docs/features/feature-guides/applications)
- [Data access workflows](https://docs.datahub.com/docs/managed-datahub/workflows/access-workflows)
- [Dataset deprecation API tutorial](https://docs.datahub.com/docs/api/tutorials/deprecation/)

## Native platforms and close products

| Source | Checked surface | Used for |
|---|---|---|
| [Looker Content Validator](https://docs.cloud.google.com/looker/docs/content-validation) | page updated 2026-07-17 | native validation, replacement scope, no-undo and edge-case warnings |
| [Looker content-validation API](https://docs.cloud.google.com/looker/docs/reference/looker-api/latest/methods/Content/content_validation) | API `4.0.26.12` | validation request and result contract |
| [Looker API](https://docs.cloud.google.com/looker/docs/reference/looker-api/latest) | API `4.0.26.12` | supported saved-content operations |
| [Atlan lifecycle workflow](https://docs.atlan.com/product/capabilities/atlan-ai/use-cases/mcp-use-cases-lifecycle-management) | live documentation | deprecation impact, owners, communication, and lifecycle competition |
| [Datafold Migration Agent](https://docs.datafold.com/data-migration-automation/datafold-migration-agent) | live documentation | SQL translation, self-correction, and data-parity competition |
| [Datafold overview](https://docs.datafold.com/welcome) | live documentation | data knowledge graph and agent positioning |
| [dbt Wizard](https://www.getdbt.com/product/dbt-wizard) | live product page | dbt-native refactoring and validation competition |

## Local evidence source

The preceding evidence repository was inspected at commit
`7ef9f58c9a081169e5a337b4ad2cc13fc35e511c`.

Relevant stable observations are summarized in
[EVIDENCE_BASELINE.md](../EVIDENCE_BASELINE.md). Raw logs and service state are
not copied into this repository until phase 00 identifies the minimum
public-safe artifacts required for reproducibility.

## Interpretation rules

- A documentation statement proves a documented capability, not every
  behavior of a deployed version.
- Absence from public documentation is not proof that a private product
  capability does not exist.
- Open-source tool claims must be checked against the repository revision and
  the running server.
- DataHub Cloud features must not be presented as DataHub Core behavior.
- Fixtures prove our code path, not the external service.
- Market findings are updated when primary product documentation changes.
