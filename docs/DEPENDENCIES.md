# Dependency review

The initial implementation keeps policy, hashing, path checks, state, and
artifact generation in the Python standard library. Two runtime dependencies
cover formats whose edge cases should not be reimplemented locally.

| Package | Purpose | License | Compatibility |
|---|---|---|---|
| PyYAML | Parse the operator-facing YAML specification with `safe_load` | MIT | compatible with Apache-2.0 |
| jsonschema | Execute the versioned Draft 2020-12 contracts | MIT | compatible with Apache-2.0 |

The build backend and development tools are not imported at runtime:

| Package | Purpose | License | Compatibility |
|---|---|---|---|
| hatchling | Build standard source and wheel distributions | MIT | compatible with Apache-2.0 |
| pytest | Execute successful and refusal-path tests | MIT | compatible with Apache-2.0 |
| Ruff | Lint and formatting verification | MIT | compatible with Apache-2.0 |
| mypy | Static type checking | MIT | compatible with Apache-2.0 |
| types-PyYAML | Type information for PyYAML | Apache-2.0 | same license as this repository |
| types-jsonschema | Type information for jsonschema | Apache-2.0 | same license as this repository |

Versions are constrained in `pyproject.toml` and resolved exactly in
`uv.lock`. A dependency update requires rerunning the full repository checks
and reviewing the resolved license metadata before evidence is promoted.
