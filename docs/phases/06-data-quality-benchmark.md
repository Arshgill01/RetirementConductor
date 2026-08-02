# Phase 06 — DataHub evidence-quality benchmark

## Outcome

Retirement Conductor is evaluated against pinned official DataHub hackathon
datasets and deterministic synthetic truth sets. The same campaign engine must
distinguish complete from partial, live from fixture, metadata freshness from
data freshness, exact from table-only lineage, and valid from quality-failing
replacement evidence without producing false readiness.

## Dependencies

- phase 04 complete vertical;
- phase 02 live DataHub Core inventory and publication boundary;
- phase 03 Git/dbt mutation and native validation;
- public datasets with verified revision, license, and checksum;
- disposable local DataHub Core, SQLite/DuckDB, Git, and dbt resources.

No external paid service, production data, Looker boundary, or private
credential is required.

## Scope

In scope:

- official `fiction-retail`, `nyc-taxi`, and `healthcare` datasets from the
  DataHub hackathon resources page;
- a pinned dataset registry and ignored content-addressed cache;
- deterministic clean and adversarial field-replacement variants;
- an independent inventory, fault, quality, and decision oracle;
- live local DataHub ingestion and direct aspect reread;
- schema, lineage, ownership, domain, glossary, tags, quality evidence, and
  stable campaign context;
- exact Git/dbt mutation, semantic validation, reconciliation, and gate;
- benchmark metrics, public-safe evidence, and refusal explanations.

Excluded:

- Looker or another paid BI instance;
- treating generated or official sample data as production evidence;
- using owner, glossary, tag, query absence, or lineage disappearance as
  native validation;
- inventing a general data-quality product or query engine;
- committing large upstream databases or moving unverified downloads.

## Deliverables

- versioned dataset registry with upstream revision, URL, license, size, and
  SHA-256;
- acquisition and offline verification command;
- deterministic fiction-retail retirement corpus generator;
- clean, rich, late-consumer, partial, stale, table-only, ambiguous,
  incompatible, null-inflated, and semantic-drift scenarios;
- nyc-taxi source-data freshness probe;
- healthcare branch-impact probe;
- independent truth oracle and schema;
- DataHub ingestion and direct-readback harness;
- benchmark runner using the existing campaign engine;
- inspected public evidence and operator explanation;
- removal plan and compatibility inventory for the deprecated Looker surface.

## Work breakdown

1. Pin the official static-assets repository revision and record dataset
   licenses and source URLs.
2. Download only to an ignored cache, verify checksums before use, and support
   an offline verification-only mode.
3. Derive a fiction-retail field pair without mutating the upstream database.
4. Generate small, medium, and full scale profiles from one versioned seed.
5. Preserve realistic order, shipment, return, promotion, and inventory
   relationships and measure referential integrity.
6. Create a clean control and truth-labeled fault variants with exact injected
   row IDs, fields, rates, and downstream effects.
7. Compute the expected graph, evidence status, consumer dispositions, native
   validation result, and final decision through an independent oracle.
8. Ingest the generated repository/dbt and data assets into disposable
   DataHub Core with unique platform instances.
9. Emit and directly reread schema, field/table lineage, ownership, domain,
   glossary, tag, and supported quality aspects.
10. Compare every observed entity and edge with the oracle; record extra,
    missing, ambiguous, or weakened claims.
11. Use nyc-taxi to show that fresh metadata ingestion does not prove fresh
    source data.
12. Use healthcare to show selective downstream impact instead of failing or
    clearing unrelated branches.
13. Execute the isolated Git/dbt campaign through native validation,
    reconciliation, publication, and the harmless producer sentinel.
14. Execute every adversarial campaign and inspect its stable refusal.
15. Run deterministic twin generations and twin benchmark runs.
16. Generate public-safe evidence with revisions, modes, digests, recall,
    quality checks, false-readiness count, and limitations.
17. Remove Looker from the supported release surface in a separate focused
    checkpoint and rerun replay, package, upgrade, fault, and recovery checks.

## Synthetic quality contract

Every generated corpus records:

- generator and oracle schema versions;
- deterministic seed and scale profile;
- upstream dataset revision, license, and checksum;
- row counts and stable content digests per table;
- primary/foreign-key expectations and observed violations;
- distribution bounds and temporal invariants;
- exact planted fault manifest and expected causal impact;
- expected DataHub identities, graph edges, evidence statuses, consumer
  dispositions, native validation outcome, and campaign decision;
- public/private artifact classification.

The oracle must not import or call the campaign policy implementation whose
result it evaluates.

## Acceptance evidence

Required behavior:

- acquisition refuses an unpinned source, checksum mismatch, unknown license,
  missing cached asset in offline mode, and unexpected archive member;
- twin generation yields byte-identical data and oracle manifests;
- controlled graph inventory returns every expected consumer or marks the
  required source incomplete;
- unexpected consumers are retained and block until dispositioned;
- exact and table-only lineage remain distinct;
- fresh ingestion with stale native timestamps blocks;
- quality faults propagate only to their oracle-declared branches;
- ownership, tags, glossary, query absence, and disappearing edges never
  become closure evidence;
- ambiguous identity, partial pagination, incompatible type, unmapped value,
  null inflation, semantic drift, and late consumers refuse as specified;
- exact Git/dbt apply targets equal the approved target set;
- dbt parse, seed, build, and semantic tests provide the native receipt;
- the isolated clean campaign reaches `READY_TO_RETIRE` and writes one harmless
  producer sentinel;
- rich and adversarial campaigns never reach readiness;
- false-readiness count is zero;
- publication is written once and verified through agent-visible read-back;
- generated public artifacts contain no source rows, credentials, private
  paths, or fixture-as-live claims.

Required commands to implement:

```bash
make check
make phase06-data
make phase06-benchmark
make test-security
make test-faults
make test-recovery
make package
make test-install
make test-upgrade
git diff --check
```

Inspect:

- dataset registry and license/checksum receipts;
- generator quality report and fault manifest;
- independent oracle;
- DataHub ingestion reports and direct aspect rereads;
- inventory comparison and evidence envelope;
- dbt native validation receipt;
- successful and refusal campaign manifests;
- publication read-back and producer gate ledger;
- public artifact digests and secret scan;
- final package contents proving Looker is absent.

## Stop or reframe conditions

- If official dataset licensing or revision cannot be verified, do not fetch
  or distribute it; use only a documented deterministic local generator.
- If DataHub cannot reproduce the controlled expected graph, preserve the
  discrepancy as a blocker and narrow the claim to the observable surface.
- If the oracle depends on the policy implementation under test, replace it
  before accepting benchmark evidence.
- If synthetic scale adds volume without new causal or refusal coverage,
  reduce it rather than presenting row count as quality.
- If the complete Git/dbt/DataHub path stops working after the reframe, repair
  it before expanding the benchmark.

## Risks changed

- R-01 incomplete or stale catalog evidence;
- R-02 exact identity mapping;
- R-03 semantic equivalence;
- R-04 late consumers;
- R-09 report-only product pressure;
- R-10 DataHub indispensability;
- R-11 Core capability divergence;
- R-15 sensitive evidence;
- R-17 disappearing lineage;
- R-21 adoption evidence;
- R-27 trusted time;
- R-30 replacement drift;
- R-32 evidence granularity;
- R-37 contradictory connector evidence;
- R-38 synthetic benchmark circularity;
- R-39 dataset provenance and reproducibility.
- R-40 source documentation and pinned-byte divergence.
