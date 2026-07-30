# Disposable Git/dbt consumer

This public-safe dbt project is copied into an ignored workspace before use.
The workspace becomes a new local Git repository and uses DuckDB only inside
the validation sandbox.

The one authorized live migration changes `legacy_status` to the compatible
`order_status` field in `models/orders_model_00.sql`. Both seed columns contain
the same values so the singular equivalence test can detect a plausible but
semantically wrong replacement.
