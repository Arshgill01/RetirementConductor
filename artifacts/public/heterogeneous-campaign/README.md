# Heterogeneous campaign acceptance

This live-local acceptance proves that one canonical campaign can close two
different native consumers instead of treating Superset as a standalone demo.

- DataHub Core 1.6.0 holds one producer field, a seeded exact dbt field edge,
  and official Superset connector output.
- Git/dbt changes one exact model and passes native parse, seed, build, and
  tests inside the contained DuckDB validation boundary.
- Superset 6.0.0 changes one allowlisted virtual dataset, preserves exact UUID
  identity, and passes forced saved-chart semantic parity.
- The campaign accepts both live receipts and becomes `READY_TO_RETIRE`.
- Authorized Superset compensation makes that consumer `STALE` and the same
  campaign `UNSAFE`.

Start with [`index.json`](index.json) and [`evidence.json`](evidence.json).
This is campaign-integrated experimental evidence, not a second complete
producer-gated path: gate-time native Superset refresh remains unimplemented,
and no production or independent-operator claim is made.
