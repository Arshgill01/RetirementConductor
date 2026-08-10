# Native downstream breakage outcome lab

This runbook exercises CP-04 in disposable PostgreSQL and Apache Spark
containers. It demonstrates an operational consequence only: dropping
`retirement_lab.orders.legacy_status` breaks the exact Spark/JDBC workload
that reads it, while a replacement-aware workload remains healthy. It does
not integrate DataHub or Retirement Conductor and does not authorize a
producer action.

## Safety boundary

- Docker Compose projects, networks, and named volumes are unique to each run.
- No host port is published.
- PostgreSQL and Spark images are pinned by immutable digest.
- The PostgreSQL JDBC jar is downloaded from its frozen Maven Central URL and
  accepted only after size, SHA-256, and manifest-version verification.
- Reader passwords are random runtime values. They are never written to public
  evidence or source files.
- `legacy_reader` and `replacement_reader` have only database connect, schema
  usage, and table select privileges.
- Raw Compose logs and native errors remain under ignored
  `.retirement-conductor/native-breakage-lab/raw/` state.
- The only destructive statement is bounded to the disposable container table:
  `ALTER TABLE retirement_lab.orders DROP COLUMN legacy_status`.

Do not point this lab at an external database. The Compose file has no setting
for an external producer endpoint.

## Frozen contract

The tracked contract at
`fixtures/native-breakage-lab/contract.json` fixes the generator version,
seed, row count, allowed statuses, expected schema and result digests, image
identities, JDBC asset, workload identities, and expected outcomes. The runner
hashes the contract, Compose file, initialization SQL, and Spark workload
before starting a service.

Public evidence contains only schema metadata, counts, safe whole-result
digests, normalized error category, SQLSTATE, and exit code. It contains no
source rows or unrestricted native error text.

## Run the complete acceptance

Prerequisites are Docker Engine with Compose and outbound HTTPS for the first
JDBC cache fill. Subsequent runs reuse the checksum-verified ignored cache.

```bash
uv run python scripts/run_native_breakage_lab.py run
```

The command performs, in order:

1. two clean unsafe-action sequences;
2. full removal and deterministic reconstruction between them;
3. one caller-denied action control;
4. two simultaneous projects proving network and credential isolation;
5. teardown of every disposable service and volume;
6. generation and structural scanning of public-safe evidence.

The prevented-action hook is the runner's explicit
`DENIED_BY_CALLER` branch. It deliberately records no reason or policy claim;
CP-05 can supply the decision and consume the native observations.

## Verify tracked evidence

```bash
uv run python scripts/run_native_breakage_lab.py verify
uv run pytest -q tests/unit/test_native_breakage_evidence.py
uv run python scripts/check_public_artifacts.py
uv run python scripts/check_secrets.py
make check
```

Inspect `artifacts/public/native-breakage-outcome-lab/index.json` and the
referenced artifacts after the commands pass. A `KEEP_SPARK` recommendation is
valid only when both unsafe sequences attribute exit 42 to SQLSTATE `42703`
for the exact missing field, the replacement digest stays stable, the denied
control stays healthy, reconstruction matches, isolation passes, and the
public scan is clean.

## Cleanup after interruption

Normal and failing scenarios use `finally` teardown. If the host process is
killed, list only CP-04 projects before removing them:

```bash
docker compose ls --format json | grep rc-cp04
```

For each exact project name returned, run:

```bash
docker compose -p PROJECT -f deploy/native-breakage-lab/docker-compose.yml down --volumes --remove-orphans
```

Never use an empty project value or broad Docker prune command. Teardown
removes disposable containers, networks, and database volumes but leaves the
tracked public evidence intact.
