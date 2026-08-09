# WS-04 — kill-gated Apache Superset native executor

## Objective

Prove that the campaign and receipt protocol can coordinate a second native
authority by migrating one exact Apache Superset consumer, executing it in
Superset, reconciling fresh DataHub metadata, and refusing closure whenever
the native or graph evidence is insufficient.

This is a high-upside, high-risk workstream. It must start with a real-system
feasibility gate and stop cleanly if exact evidence cannot be obtained. It is
not permission to add a mock adapter or another fixture-only claim.

Official surfaces supporting the feasibility check:

- DataHub’s Superset connector ingests dashboards, charts, datasets,
  ownership context, tags, stateful deletion, and table-level lineage:
  <https://docs.datahub.com/docs/generated/ingestion/sources/superset>.
- Superset exposes chart and dataset read/update endpoints plus native chart
  execution through `/api/v1/chart/{pk}/data/` and query-context execution
  through `/api/v1/chart/data`:
  <https://superset.apache.org/developer-docs/api/charts/>.

The DataHub connector currently documents table-level, not field-level,
lineage. That limitation is central to the gate below.

## Phase 0 — ninety-minute feasibility gate

Use a disposable pinned Superset container and the existing disposable DataHub
Core. Create one virtual dataset or saved-query-backed chart that actually
references `legacy_status`.

Before writing product code, capture and inspect:

1. Superset version and API authentication mode;
2. exact native chart, dataset, database, and query identities;
3. before-state chart or query configuration containing the exact legacy
   field reference;
4. successful forced native chart/query execution and safe output shape;
5. DataHub connector output for the chart, dashboard, dataset, ownership, and
   lineage;
6. a deterministic one-to-one mapping from the DataHub entity to the exact
   Superset native identity;
7. whether the connector or a separate native claim can honestly identify the
   exact field dependency without treating table lineage as field lineage;
8. a bounded reversible update that changes only the one selected native
   object;
9. a second native execution after the update;
10. a reingestion and direct DataHub reread showing the updated context and all
    connector limitations.

The feasibility gate passes only if all of these are true:

- DataHub materially contributes discovery or cross-system identity;
- native identity is exactly one-to-one;
- the old field reference is directly inspectable in Superset;
- the mutation can be constrained to one allowlisted object;
- before and after fingerprints can be computed from stable native content;
- native chart/query execution supplies more evidence than HTTP success;
- semantic output parity or an explicitly approved semantic change can be
  measured safely;
- compensation can restore the exact before state without overwriting drift;
- reingestion is repeatable and its table-level limitation remains explicit.

If any item fails, record the reason and stop. Do not implement the executor.

## Implementation after the gate

Keep the boundary concrete. Do not extract a generic adapter framework.

Suggested files:

- `src/retirement_conductor/superset.py`;
- `src/retirement_conductor/superset_config.py`;
- `src/retirement_conductor/superset_workflow.py`;
- a pinned disposable Superset compose profile and seed script;
- focused unit, integration, security, recovery, and live-local tests;
- one runbook and evidence generator.

The lifecycle must match the existing native contract:

### Preflight and identity

- authenticate with least privilege;
- record effective capabilities without secret values;
- resolve one DataHub consumer to one native chart/dataset/query identity;
- capture source version, stable content fingerprint, referenced field,
  related dashboards, and recovery material;
- refuse zero or multiple matches.

### Plan and authorization

- plan one exact legacy-to-replacement edit;
- state the native object, before/after fingerprints, expected query, semantic
  comparison, and compensation;
- bind the exact object and operation into the plan digest;
- require external human approval and explicit apply capability.

### Apply

- reread identity, version, and fingerprint immediately before mutation;
- update only the approved object through the native API;
- reread and compare the actual target set and content;
- treat timeout or transport loss as outcome unknown and recover by reread;
- never retry blindly.

### Validate

- force native chart or query execution against the replacement field;
- verify the response is complete and contains the expected result shape;
- compare safe before/after output semantics under declared tolerance;
- record Superset and database versions, operation, timing, counts, and
  artifact digests;
- do not accept a screenshot or API status as validation.

### Compensate

- require the expected post-apply fingerprint;
- restore the exact before state;
- execute and verify it natively;
- refuse rather than overwrite intervening owner changes.

### Receipt and reconciliation

- emit the existing versioned consumer receipt with adapter `superset` only
  after plan, apply, and validation artifacts agree;
- reingest the selected Superset scope into DataHub;
- directly reread the chart/dataset/lineage entities;
- retain the documented table-level limitation;
- never treat disappearance as closure.

## Live acceptance

Prove both success and refusal:

1. DataHub inventory or table-level context reveals the Superset consumer and
   the native adapter proves its exact field reference.
2. Apply refuses before approval.
3. One approved object changes.
4. Native chart/query execution and semantic comparison pass.
5. A Superset receipt closes only that exact consumer.
6. Fresh DataHub reingestion and direct reread complete.
7. The campaign decision changes only if every other consumer and evidence
   source is acceptable.
8. Source drift, ambiguous identity, API timeout, execution failure, semantic
   drift, connector failure, and table-only evidence each refuse correctly.
9. Compensation succeeds once and refuses an intervening-owner-change case.

## Integration rule

The controlling product currently names Git/dbt as the sole automated
executor. Do not change that claim until the live acceptance above passes and
the generated artifacts are inspected. If it passes, the integration owner
must update the goal, product, architecture, contracts, risks, decisions,
traceability, evidence ledger, deployment, package, and public non-claims in
one coherent scope change.

## Stop conditions

Stop and preserve only an honest feasibility report if:

- exact field dependence cannot be established without fabricated lineage;
- native identity relies on display-name matching;
- only a broad dashboard or multi-object update is possible;
- validation cannot exceed an HTTP-success or screenshot claim;
- compensation cannot be proven safely;
- a real disposable Superset cannot be run;
- the implementation needs production credentials or a paid service;
- the connector limitation is hidden to make the demo look complete.
