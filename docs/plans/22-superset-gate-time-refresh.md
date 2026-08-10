# CP-02 — Superset gate-time native refresh

## Objective

Build a read-only, failure-closed verifier that can independently reconstruct
the accepted Superset receipt's critical native facts immediately before a
producer action. This closes the exact limitation that currently keeps
Superset campaign-integrated but experimental.

## Product question

Can the final gate prove that the exact Superset dataset, saved chart, SQL
mapping, native identity, and semantic result still match the accepted receipt
without trusting the earlier receipt or mutating Superset?

## Scope

Implement a standalone verifier that CP-05 can call from
`ProducerGateWorkflow._verify_ready_state`. It must consume only explicit
campaign artifacts and secret-safe runtime settings, and return one normalized
gate-time source observation.

The verifier must:

- authenticate with a read-only Superset principal;
- require loopback disposable scope for live acceptance;
- reread the exact dataset, chart, and database identities;
- verify dataset, chart, and database UUIDs rather than only integer IDs;
- verify the chart still points to the exact dataset;
- compare the current dataset SQL/source fingerprint with the accepted
  post-apply fingerprint;
- verify the legacy-field reference remains removed and the replacement-field
  mapping remains exact;
- force native saved-chart execution at gate time;
- compare schema, row count, ordering contract, and safe semantic result digest
  with the accepted validation receipt;
- produce evidence compatible with the canonical evidence envelope's source
  scope and freshness checks;
- refuse on authentication, permission, availability, identity, source,
  semantic, or evidence drift;
- never call a mutation API.

Do not edit the shared gate, schemas, CLI, MCP, or canonical documents on this
branch. Produce the smallest integration hunk for CP-05.

## Binding requirements

The gate-time verifier must bind to the existing accepted campaign data, not
an operator-selected replacement object. Required inputs include:

- consumer ID and DataHub native identity;
- accepted plan digest and receipt digest;
- dataset ID and UUID;
- chart ID and UUID;
- database ID and UUID;
- accepted post-apply dataset fingerprint;
- accepted semantic validation artifact/digest;
- Superset adapter and server versions;
- safe endpoint/configuration digest;
- expected evidence-source identity and scope.

Credentials are runtime-only. Their values must not enter plans, receipts,
manifests, logs, or public evidence.

## Fresh observation contract

Return a normalized observation containing at least:

- source ID and mode;
- observed time and maximum permitted age;
- permissions and pagination/capability statement;
- exact native identities;
- current source fingerprint;
- forced execution result digest;
- match/mismatch result for every accepted binding;
- artifact IDs and canonical observation digest;
- explicit limitations.

The verifier must not decide campaign readiness. It returns evidence or raises
a stable refusal for the deterministic gate.

## Acceptance matrix

### Unchanged control

- Run the existing bounded Superset mutation and native validation.
- Build the verifier only from its accepted plan/receipt and runtime settings.
- Reread the live dataset, chart, database, and forced execution.
- Produce an exact gate-time observation whose bindings match.
- Repeat read-only verification and prove no native object changed.

### Refusal cases

At minimum prove refusal for:

- dataset SQL changed after accepted validation;
- legacy field reintroduced;
- replacement mapping changed;
- chart moved to another dataset;
- chart query/context changed and semantic output diverged;
- dataset UUID mismatch;
- chart UUID mismatch;
- database UUID mismatch;
- intervening owner edit;
- dataset, chart, or database deleted;
- authentication failure;
- read permission removed;
- Superset outage or timeout;
- unexpected response shape;
- accepted receipt or semantic artifact tampered;
- server or adapter version drift when policy requires an exact version;
- stale observation under the trusted clock.

Every injected native drift must be compensated or the disposable environment
recreated before the next case. Evidence must distinguish source mismatch from
source unavailability.

## DataHub relationship

The final gate already reruns DataHub inventory. This verifier does not replace
that graph check. Its task-local acceptance must demonstrate how CP-05 will
bind:

1. current DataHub membership and exact Superset native identity;
2. the accepted Superset consumer receipt;
3. the fresh native Superset observation.

If the official DataHub connector remains table-level for a field fact, keep
that limitation explicit. Native Superset SQL/execution proves the consumer
state; DataHub proves cross-system identity and graph membership. Neither may
silently substitute for the other.

## Evidence

Create task-local public evidence under:

```text
artifacts/public/superset-gate-refresh/
```

The index must include:

- exact Superset and connector versions;
- accepted plan/receipt digests;
- unchanged observation digest;
- refusal matrix with stable categories;
- mutation-call count during verification, which must be zero;
- direct native reread and forced execution proof;
- DataHub identity relationship and limitations;
- canonical self-digest.

Raw API responses, credentials, cookies, query results, and machine paths stay
ignored and private.

## Owned files

Prefer new or narrowly task-owned paths:

- `src/retirement_conductor/superset_gate.py`;
- focused additions to `superset.py` only when a read method is genuinely
  missing and does not alter mutation behavior;
- `scripts/run_superset_gate_acceptance.py`;
- `tests/unit/test_superset_gate.py`;
- `docs/plans/integration-notes-superset-gate.md`;
- `artifacts/public/superset-gate-refresh/`.

Do not edit `gate.py`, shared JSON schemas, existing heterogeneous evidence, or
canonical documentation.

## Validation

Run focused unit tests, the full live-local drift matrix, inspect native state
before and after the read-only verifier, then run `make check`.

## Completion recommendation

Return one of:

- `KEEP` — unchanged verification passes and every required drift/outage
  refuses without mutation;
- `SIMPLIFY` — fewer bindings provide the same demonstrated safety;
- `REMOVE` — exact native reconstruction is not possible from accepted
  artifacts;
- `INCONCLUSIVE` — live Superset acceptance could not be completed.
