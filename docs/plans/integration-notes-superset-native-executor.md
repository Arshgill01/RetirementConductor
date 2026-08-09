# WS-04 Superset native executor — integration notes

## Result

The feasibility gate passed on 2026-08-09 against a disposable Apache Superset
6.0.0 container and DataHub Core 1.6.0. Product code was implemented only after
all ten gate observations were inspected.

The workstream branch intentionally does **not** change `GOAL.md`, `STATUS.md`,
the evidence ledger, shared architecture/contracts/risks/decisions, package
registration, campaign state, gate policy, or public product claims. Those are
integration-owner decisions under the winning-workstreams conflict boundary.

## Feasibility gate evidence

1. Superset self-reported 6.0.0. Authentication was database login followed by
   JWT bearer and CSRF tokens.
2. Native identities were captured for database 1, virtual dataset 1, chart 1,
   and dashboard 1, including each UUID.
3. The exact virtual-dataset SQL contained one `legacy_status` reference.
4. Forced native chart execution returned six complete rows with columns
   `id`, `status`, and `amount`; its safe output digest was recorded.
5. The official DataHub 1.6.0 Superset connector emitted the selected dataset,
   chart, dashboard, ownership context, and lineage without warnings or
   failures.
6. The connector's dataset URL supplied `datasource_id=1`; a native reread then
   established the immutable dataset/database UUIDs. No display-name match was
   used for apply identity.
7. Direct native SQL established exact field dependence. The connector contract
   documents table-level lineage; its observed parser-derived fine-grained edge
   was retained only as corroboration for this SQL.
8. One dataset-only `PUT` changed the stable SQL content fingerprint while all
   immutable identities and the target set stayed fixed.
9. A second forced native execution returned the same complete semantic output.
10. Repeat ingestion and direct GMS rereads showed the replacement-field edge,
    no legacy-field edge, and unchanged chart/dashboard identities while
    preserving the documented table-level limitation.

The exact before state was restored through the same API with native execution.
A separate live owner edit caused `COMPENSATION_CONFLICT`; the executor did not
overwrite it. The disposable object was then explicitly cleaned back to the
recorded before state.

## Implemented boundary

- `superset_config.py`: loopback-only, secret-safe, apply-off-by-default settings
  and an exact dataset allowlist.
- `superset.py`: authenticated native client; DataHub/native identity preflight;
  stable snapshots; one-token plan; drift-safe apply; timeout reread; forced
  chart validation; semantic comparison; receipt; compensation; and fresh
  source reconciliation.
- `superset_workflow.py`: existing durable approval validation before apply or
  compensation.
- Pinned compose, synthetic initialization SQL, official connector recipe, and
  idempotent authenticated seed script.
- Focused refusal/recovery tests and a live-artifact evidence generator.

## Refusal coverage

The focused suite proves missing approval, disabled apply, ambiguous DataHub
identity, source drift, timeout-before-update outcome unknown,
timeout-after-update exact reread recovery, native execution failure, semantic
drift, table-only DataHub evidence, safe compensation, and owner-change
compensation conflict. Live-local probes additionally established missing
approval, one exact approved mutation, semantic parity, fresh connector reread,
successful compensation, and preservation of an intervening owner edit.

Connector unavailability was exercised separately with an unreachable endpoint;
no receipt or reconciliation was emitted. The successful connector was rerun
afterward to establish fresh evidence.

## Integration-owner work

Do not register this executor merely because the branch exists. The integration
owner should first inspect `artifacts/public/superset/ws04-evidence.json` and the
private live-local artifacts, then decide whether the narrow scope is worth
adding. If accepted, update the controlling product claim and all documents
named by the workstream integration rule in one coherent change. Registration
also needs campaign storage/event projection, CLI and agent surfaces, gate
receipt binding, deployment packaging, security-model capability separation,
and a test proving Superset closure cannot make the campaign ready while any
other consumer or evidence source is unacceptable.

Until that work lands, Superset receipts are standalone workstream evidence and
cannot change the producer retirement decision. This conservative non-effect is
intentional.
