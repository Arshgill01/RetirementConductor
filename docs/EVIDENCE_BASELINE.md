# Evidence baseline

This document separates what has already been observed from what the product
still has to prove. It is a handoff summary, not a replacement for raw
artifacts.

## Proven in the preceding live DataHub and dbt experiment

Environment:

- DataHub Core `v1.6.0`;
- DataHub CLI `1.6.0`;
- official cross-platform ecommerce datapack;
- pinned open-source DataHub MCP server;
- disposable dbt project backed by DuckDB.

Observed:

| Claim | Observation |
|---|---|
| DataHub materially expanded inventory | Repository evidence contained 1 consumer; live DataHub evidence contained 35 |
| The added scope was consequential | A live lineage path reached an executive Power BI report absent from the repository |
| DataHub changed the decision | Repository-only policy allowed retirement; augmented policy refused it |
| One real consumer crossed mutation | A dbt model changed from the legacy source to the replacement |
| Mutation was concurrency guarded | A changed source hash refused before overwrite |
| Replacement validity was checked | A nonexistent replacement column refused |
| Native validation ran | dbt parse, build, and five tests passed |
| Unknown consumers remained honest | 31 BI consumers stayed opaque and 3 other consumers stayed unresolved |
| Lifecycle was protected | The source asset remained active while blockers existed |
| Shared memory worked | One stable refusal summary was updated and read back through DataHub's agent surface |
| Narrow reruns were stable | Inventories, policy result, and evidence digests reproduced |

Evidence-bearing commits in the experiment repository:

- `8175f7f` — original repository foundation;
- `a251cb7` — completed live DataHub/dbt evidence;
- `b5233ca` — fail-closed Looker adapter;
- `7ef9f58` — refreshed DataHub reconciliation and Looker access boundary.

## Historical deterministic Looker boundary — superseded

The following fixture observations remain true as implementation history, but
Looker is no longer supported and none of them is current acceptance evidence.

Implemented and tested:

- exact saved-Look identity and allowlist checks;
- documented query creation and saved-Look update path;
- source and schedule fingerprints;
- plan, apply, validate, compensate, and receipt lifecycle;
- authentication and common HTTP failure handling;
- stale source, invalid replacement, target expansion, validation failure,
  repeated apply, rollback, and fixture-receipt refusal;
- deterministic campaign combination with the proven dbt consumer.

This establishes implementation behavior, not live product proof.

## Proven under the current goal

- official dataset acquisition pinned by revision, license, and checksum;
- a deterministic fiction-retail retirement corpus and independent oracle;
- nyc-taxi native freshness and healthcare branch-selectivity truth;
- controlled graph recall and zero false readiness across 14 scenarios;
- a post-removal live-local DataHub, Git/dbt, publication, and gate campaign;
- removal of the deprecated adapter from runtime and release package content;
- post-removal least-privilege, fault, recovery, copied-store, dependency,
  license, secret, and public-artifact checks;
- reproducible post-removal package, four clean Python installs,
  upgrade/rollback, confirmed removal, and installed-wheel live reference.

## Not yet proven under the current goal

- user frequency, willingness to adopt, and economic value;
- external-receipt usefulness for non-repository consumers.

## Promotion policy

Phase 00 may selectively promote:

- state and disposition vocabulary;
- pure deterministic policy behavior;
- content-hash preconditions;
- adapter lifecycle semantics;
- receipt integrity rules;
- failure fixtures that correspond to real source behavior.

It must not copy:

- experiment-specific paths or URNs;
- raw retained service state;
- local credentials or tokens;
- verdict vocabulary used to evaluate the experiment itself;
- report markup as application architecture;
- fake evidence presented as live behavior.

Every promoted component receives product-level naming, tests, and a link back
to the observation it preserves.
