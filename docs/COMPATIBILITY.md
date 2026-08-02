# Compatibility matrix

Compatibility claims are split between package installation and live
integration. An install result does not prove a remote source boundary, and a
fixture never becomes live evidence.

## Executed package boundary

| Surface | Executed boundary | Evidence status |
|---|---|---|
| Host OS | Linux, x86_64, glibc 2.43 | clean install, upgrade, removal, and reference exercised |
| Python | CPython 3.11.15 | clean install and complete reference exercised |
| Python | CPython 3.12.13 | clean install and built-in reference exercised |
| Python | CPython 3.13.14 | clean install and built-in reference exercised |
| Python | CPython 3.14.4 | clean install and built-in reference exercised |
| Package | `retirement-conductor` 0.2.0 wheel and source archive | reproducible build and archive inspection exercised |
| State | local SQLite, one resolved path, one writer | backup, restore, migration, copied-state refusal, and confirmed removal exercised |

macOS, Windows, musl Linux, shared filesystems, multiple writers, and a product
container have not been executed and are unsupported. The wheel is pure
Python, but that packaging property is not evidence for an unexecuted
operating boundary.

## Executed integration boundary

| Integration | Executed version or identity | Evidence status |
|---|---|---|
| DataHub Core | GMS v1.6.0 in the pinned disposable Core composition | live exact identity, cache-bypassed inventory, reconciliation, publication, and read-back exercised |
| DataHub MCP | package 0.6.0 from source commit `9a6946daa7d30eb481c82dd8ee5e15ae6526a3c9` | live loopback MCP capability and read-back exercised |
| Git | host Git reported by Phase 08 compatibility evidence | disposable review branches, preconditions, rollback, and gate provenance exercised |
| dbt | dbt-duckdb 1.10.1 | native parse, seed, build, semantic test, failure, and rollback exercised |
| DuckDB | version resolved by the pinned dbt runtime | disposable local warehouse only |
| Linux validator | bubblewrap reported by Phase 08 compatibility evidence | network, filesystem, environment, process, and resource boundary probes exercised |
| Container runtime | Docker client reported by Phase 08 compatibility evidence | used only for disposable DataHub Core services |

Core v1.6.0 omits requested graph-cache freshness metadata and its agent-visible
summary read-back can lag a successful write. Retirement Conductor bypasses
the lineage cache for the complete consumer universe, retains that limitation,
and polls only publication read-back within a fixed bound.

## Planned or optional boundaries

| Surface | Boundary | Remaining evidence |
|---|---|---|
| Official dataset benchmark | pinned `fiction-retail`, `nyc-taxi`, and `healthcare` inputs plus deterministic truth oracle | registry, checksums, acquisition, generator, live local ingestion, and Phase 06 evidence are not yet run |
| DataHub Cloud | optional configuration boundary | authenticated Cloud capability, paging, freshness, publication, and source-version behavior |

Looker is not a planned or supported compatibility boundary. DataHub Cloud
enhancements are optional; the supported vertical and benchmark run on the
executed Core boundary.

## Version policy

The matrix names exact executed versions. A newer Python, DataHub, dbt,
DuckDB, MCP, Git, bubblewrap, or Docker version is unverified until the
applicable package, native, refusal, and end-to-end checks pass and public-safe
evidence is regenerated. See [Maintenance](MAINTENANCE.md).
