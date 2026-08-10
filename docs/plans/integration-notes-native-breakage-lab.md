# CP-04 integration notes — native downstream breakage outcome lab

## Scope and frozen boundary

- Planning base: `b8a839acd0b411d905fa0ed142838cd76ab618f4`
- Workstream branch: `codex/cp-04-native-breakage-outcome-lab`
- Owned implementation: `deploy/native-breakage-lab/`,
  `fixtures/native-breakage-lab/`, `scripts/run_native_breakage_lab.py`, and
  `tests/unit/test_native_breakage_evidence.py`
- Owned evidence/docs: `artifacts/public/native-breakage-outcome-lab/`,
  `docs/runbooks/NATIVE_BREAKAGE_LAB.md`, and this file

No product source, shared deployment, package dependency, canonical evidence,
DataHub boundary, or Retirement Conductor campaign behavior is changed.

## CP-05 handoff

Use `consumer-descriptor.json` as a public-safe native input description. It
binds the Apache Spark version and job identity, producer dataset identity,
exact `legacy_status` use, observed execution time and success digest, source
definition digest, evidence mode, and limitations.

The descriptor is not lineage evidence. CP-05 must ingest an independently
constructed DataHub aspect and directly reread that aspect before using the
consumer in any campaign. Integration must not copy CP-04's successful native
observation into a DataHub or campaign closure claim.

The prevented-action hook is `DENIED_BY_CALLER`; it executes no statement and
does not decide why the action was denied. CP-05 may call this branch after its
own authority decides refusal, then compare the native schema and workload
observations with its unsafe-action arm.

## Evidence and recommendation

The live-local lab passed against disposable PostgreSQL 16.14, Apache Spark
3.5.3, and PostgreSQL JDBC 42.7.4. The tracked input freeze is
`sha256:e1bcca73b76984be7195778da1eeadcbbd1280aabb79be929d1e666199037813`.

Both clean unsafe-action runs observed the same sequence:

- the legacy and replacement Spark jobs succeeded over 128 rows with semantic
  digest
  `sha256:9f977475388edb756d84c140c02b315f82e669615047f0861c1e84b35657a078`;
- one exact `DROP COLUMN` executed in that disposable project;
- native schema reread proved `legacy_status` absent;
- the legacy job returned `LEGACY_COLUMN_MISSING`, PostgreSQL SQLSTATE
  `42703`, and process exit 42;
- the replacement job still succeeded with the unchanged semantic digest.

The second run began only after the first project, network, database volume,
and containers were removed. Its pre-drop schema and both workload digests
matched the first run exactly. The denied control executed zero destructive
statements, kept the original schema digest, and kept both workloads healthy.
Two simultaneous projects shared no network and rejected the other project's
reader credential over PostgreSQL's SCRAM host boundary.

Public index:
`artifacts/public/native-breakage-outcome-lab/index.json`

Canonical index self-digest:
`sha256:9ffd98967d4388d6c547f31e627fbc2b2d5336041e0d29e208c681c1a93e7238`

The final branch commit is reported in the handoff because a commit cannot
embed its own identity. Evidence was produced and inspected from the final
implementation tree before that commit.

## Failure-closed setup observations

Two startup defects refused before any destructive statement and did not
publish evidence:

1. Restrictive host umask permissions initially prevented the non-root
   PostgreSQL container from reading the mounted init directory. The runner
   now uses container-readable tracked modes and tears down even when startup
   fails.
2. The checksum-verified JDBC cache file initially remained mode `0600`, so
   Spark refused with a native file-permission error before opening JDBC. The
   cache verifier now sets read-only-container-compatible mode `0644`.

The first isolation probe then exposed PostgreSQL's container-local trust rule:
a loopback client cannot test password separation. That attempt refused
promotion. The retained probe uses a separate pinned PostgreSQL client
container over each Compose network and therefore exercises SCRAM host
authentication. Raw diagnostics remain ignored runtime state.

## Validation

- `uv run python scripts/run_native_breakage_lab.py run` — passed with
  `NATIVE_BREAKAGE_OUTCOME_LAB_PASSED` and `KEEP_SPARK`.
- `uv run python scripts/run_native_breakage_lab.py verify` — passed all
  canonical artifact digests and the structural public scan.
- `uv run pytest -q tests/unit/test_native_breakage_evidence.py` — 5 passed.
- `uv run python scripts/check_public_artifacts.py` — passed, 98 files.
- `uv run python scripts/check_secrets.py` — passed, 448 text files.
- `make check` — passed Ruff, formatting, strict mypy over 98 source files,
  266 tests, repository validation, secret/public scans, source and wheel
  builds, and `git diff --check`.

## Recommendation and limitations

`KEEP_SPARK`. The pinned Spark/JDBC workload reproducibly attributes native
downstream failure to the exact dropped field, so the generic fallback was not
used.

The result remains disposable live-local evidence over deterministic fixture
data. It does not establish a DataHub identity, campaign causality, production
coverage, customer value, or the CP-05 three-arm comparison. PostgreSQL
container-local connections use the image's trust initialization rule; the
credential-isolation claim is specifically bound to the exercised
separate-container SCRAM network path.
