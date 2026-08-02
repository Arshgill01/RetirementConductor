# DataHub evidence-quality benchmark runbook

This runbook describes the Phase 06 replacement controlled by `GOAL.md`. The
commands are acceptance targets until their implementation and evidence are
committed. It requires no paid service, production endpoint, or private data.

## Boundaries

- DataHub Core runs on the existing project-isolated loopback composition.
- Official inputs come only from the versioned dataset registry.
- Large source databases and generated medium/full corpora stay ignored.
- Git/dbt and DuckDB are disposable local native-validation boundaries.
- The independent oracle never imports campaign policy code.
- Looker is not used.

## Prepare pinned inputs

```bash
retirement-conductor benchmark data acquire \
  --registry fixtures/data-quality/datasets.json \
  --cache .retirement-conductor/datasets

retirement-conductor benchmark data verify \
  --registry fixtures/data-quality/datasets.json \
  --cache .retirement-conductor/datasets \
  --offline
```

Acquisition must verify URL, upstream revision, license, size, SHA-256, and
allowed archive members before publishing a content-addressed cache entry. A
moving or mismatched source refuses before parsing or execution.

## Generate the corpus and oracle

```bash
retirement-conductor benchmark data generate \
  --registry fixtures/data-quality/datasets.json \
  --cache .retirement-conductor/datasets \
  --seed 20260802 \
  --scale medium \
  --output .retirement-conductor/benchmark/generation-a

retirement-conductor benchmark data generate \
  --registry fixtures/data-quality/datasets.json \
  --cache .retirement-conductor/datasets \
  --seed 20260802 \
  --scale medium \
  --output .retirement-conductor/benchmark/generation-b

retirement-conductor benchmark data compare \
  --left .retirement-conductor/benchmark/generation-a \
  --right .retirement-conductor/benchmark/generation-b
```

The output contains clean and fault variants, a private-safe fault manifest,
an independent oracle, aggregate quality statistics, and stable digests. Run
generation twice in separate ignored directories and compare every canonical
digest before promotion.

## Run against disposable DataHub Core

```bash
make datahub-core-up
retirement-conductor benchmark run \
  --input .retirement-conductor/benchmark \
  --profile data-quality-benchmark
```

The runner ingests schema and graph context, rereads exact aspects, compares
them with the oracle, executes the clean Git/dbt campaign, and evaluates every
adversarial refusal through the existing campaign engine.

## Acceptance

```bash
make phase06-data
make phase06-benchmark
make check
git diff --check
```

Inspect the registry receipt, generator report, oracle, DataHub direct reread,
inventory comparison, dbt receipt, decisions, gate ledger, source revisions,
artifact digests, limitations, and secret/public scans. Official or generated
rows must not enter tracked evidence.

## Cleanup

Stop the disposable Core composition with `make datahub-core-down`. Dataset
cache and generated benchmark state are retained under ignored local state for
reproducibility. Deleting them is a separate local cleanup action and is not
part of the benchmark command.
