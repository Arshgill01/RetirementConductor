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

## Phase 07 audit

On 2026-07-30, `pip-audit` 2.9.0 inspected the frozen `uv export` for every
runtime and development group. The initial scan found
`PYSEC-2026-1845` / `CVE-2025-71176` in pytest 8.4.2: predictable shared
temporary-directory handling could permit local denial of service or
privilege impact on a multi-user UNIX host.

The repository raised its pytest floor to 9.0.3 and resolved pytest 9.1.1.
The complete 217-test suite passed on the new version. The repeated audit
inspected 18 environment-applicable packages and reported zero known
vulnerabilities.

The lock contains 20 third-party package records across supported markers.
Every record resolves from the configured PyPI registry and includes
SHA-256-bound source and wheel artifacts. Runtime transitive packages
(`attrs`, `jsonschema-specifications`, `referencing`, and `rpds-py`) report
MIT metadata, as do the two direct runtime dependencies.

The acceptance command is:

```bash
make scan
```

It verifies the frozen lock and artifact provenance, audits all resolved
groups with pinned `pip-audit`, runs the repository secret scan, and reviews
every tracked public artifact. A future finding must either be removed by an
upgrade or recorded with an explicit exposure analysis and expiry; a passing
Phase 07 scan currently permits no unresolved finding.
