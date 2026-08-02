# Access requirements

This document separates public and disposable resources the implementation can
create locally from inputs only another operator can supply. The current
engineering goal has no paid-service or private-data dependency.

## Secret and data handling

- Never paste credentials into chat, tracked files, command arguments,
  process listings, screenshots, manifests, reports, or public evidence.
- Store optional protected DataHub values only in ignored `.env.local` or an
  equivalent ignored secret-reference mechanism.
- Cache official datasets only under ignored local state after revision,
  license, size, and checksum verification.
- Never commit upstream database binaries, raw source rows, generated medium
  or full corpora, private query text, or runtime campaign state.
- Public evidence contains aggregates, stable synthetic labels, modes,
  revisions, checksums, truth-oracle digests, outcomes, and limitations.

## Access available without user action

### Repository

- Working directory:
  `/home/arshdeepsingh/work/RetirementConductor`
- Remote: `https://github.com/Arshgill01/RetirementConductor.git`
- Existing Git authentication may be used for focused commits and pushes.
- Force-push, history rewrite, unrelated merge, and production release
  mutation remain excluded.

### Disposable DataHub Core

The implementation may start the pinned project-isolated DataHub Core
environment and load public-safe official and generated metadata. GMS is
published only on loopback; backing services remain on the private Compose
network.

The product configuration uses secret references equivalent to:

```text
DATAHUB_GMS_URL
DATAHUB_GMS_TOKEN
DATAHUB_UI_URL
DATAHUB_MCP_URL
DATAHUB_PLATFORM_INSTANCE
DATAHUB_GRAPH_MAX_HOPS
DATAHUB_TARGET_URN
DATAHUB_REPLACEMENT_URN
```

Loopback Core may run without a token. A protected remote endpoint would
require a user-supplied ignored secret, but it is not required by the current
goal.

### Disposable Git/dbt and data plane

The implementation may create:

- local disposable Git repositories and review branches;
- dbt projects with pinned dbt-duckdb tooling;
- SQLite and DuckDB databases derived from licensed public or generated data;
- copied no-network validation sandboxes;
- campaign stores, backups, reports, and raw evidence under ignored local
  state.

No production repository or warehouse credential is required.

### Official DataHub hackathon datasets

The authoritative resource page is
<https://datahub.devpost.com/resources>. The current goal adopts these public
inputs from `datahub-project/static-assets`:

| Dataset | Intended use | Upstream license |
|---|---|---|
| `fiction-retail` | primary clean relational field-retirement base | CC0 1.0 |
| `nyc-taxi` | source-data freshness and empty-load truth | public-domain source; transformed asset terms must be recorded |
| `healthcare` | deterministic quality faults and forked downstream impact | CC0 1.0 |

The dataset registry must pin the upstream repository commit and each required
file's SHA-256 before acquisition. Network access is allowed only for the
explicit registry URLs. Acceptance must support offline verification from the
ignored content-addressed cache and must refuse moving, mismatched, unlicensed,
oversized, or unexpected content.

The `showcase-ecommerce` datapack remains historical baseline context. It is
not loaded by the new acceptance path because the product no longer uses
Looker and the official pack includes Looker metadata. The lightweight
`bootstrap` datapack may be used for a smoke check but cannot satisfy the
evidence-quality phase.

## Looker is prohibited

Do not provision, authenticate to, ingest from, query, mutate, or request
access to Looker. Do not use the prior GCP pretrial boundary. Looker is absent
from the supported product, current acceptance, and completion contract.

Any ignored historical Looker handoff files are stale local artifacts. They
must not be used as resume instructions and may be removed through the normal
safe local-state cleanup process after the tracked product no longer
references them.

## Independent operator boundary

An independent prospective operator is still required before claiming
customer frequency, organizational value, willingness to adopt, or buyer
evidence. It is not required to complete the current engineering benchmark.

Use `docs/EVALUATION.md` and
`docs/templates/OPERATOR_OBSERVATION.md`. Store raw notes only under ignored,
access-controlled local state and promote only an inspected, redacted
observation. A model, synthetic persona, author-run reference, or repository
activity cannot satisfy this boundary.

## Current execution protocol

No external access request is active. The exact engineering resume sequence
is repository-local:

```bash
make datahub-core-up
make phase06-data
make phase06-benchmark
```

The latter two targets do not exist until Phase 06 implements them. Missing
commands are unfinished work, not external blockers.

## Capability separation

| Principal or boundary | Minimum capability | Must not have |
|---|---|---|
| DataHub inventory | exact search, schema, ownership, lineage, quality, path, and permitted query reads | campaign transaction authority or producer action |
| DataHub publisher | update and reread one stable campaign summary | source mutation or lifecycle change |
| Git/dbt planner | read one declared repository and dbt manifest | branch or file write |
| Git/dbt applier | create one review branch and change approved paths | default-branch rewrite, hooks, unrelated paths, production warehouse access |
| dbt validator | copied project and disposable local target | network, host home, source checkout, deployment secrets |
| Producer gate | exact short-lived producer invocation | reusable campaign-wide producer access |
| Dataset acquisition | registry-declared URLs and ignored cache | arbitrary URL fetching, execution from downloads, tracked binary writes |

Configuration opt-in and campaign authorization remain required even when the
native filesystem principal has broader access.
