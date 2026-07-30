# Phase 06 — Live Looker adapter

## Outcome

A consequential Looker consumer discovered through DataHub is mapped to one
exact native saved-content object, changed through a documented bounded
surface, validated inside Looker, reconciled through fresh DataHub evidence,
and joined to the same campaign as the Git/dbt receipt.

## Dependencies

- phase 04 complete vertical;
- phase 01 adapter and receipt contracts;
- disposable Looker instance, project, model, Explore, folder, saved content,
  and safe warehouse connection;
- scoped API credentials and explicit apply authority;
- disposable content ingested into DataHub.

## Scope

In scope:

- one saved Look or equally bounded saved-content object;
- exact DataHub-to-Looker identity mapping;
- read, plan, apply, validate, and compensate capability checks;
- saved-content snapshot and schedule set;
- documented API-based query/content update;
- Content Validation API;
- bounded native query execution and semantic checks;
- rollback or compensation;
- refreshed Looker ingestion and DataHub reconciliation.

Excluded:

- instance-wide blind replacement;
- undocumented private APIs;
- shared or production content;
- unrelated dashboards, alerts, schedules, and folders;
- treating a clean Content Validator result as complete semantic proof;
- fixture receipts as live acceptance evidence.

## Deliverables

- scoped Looker and LookML ingestion recipes with secret references;
- live capability and permission receipt;
- exact native identity resolver;
- source snapshot and normalized fingerprint;
- bounded plan and actual-target comparison;
- documented saved-content mutation;
- Content Validation and query-execution evidence;
- compensation evidence;
- live Looker receipt;
- before/after DataHub graph snapshots;
- combined campaign result and operator report.

## Work breakdown

1. Verify the authenticated principal and effective model and content scope.
2. Inventory the disposable project, model, Explore, folder, saved object,
   schedules, alerts, and dependencies without mutation.
3. Confirm the legacy and replacement fields exist and are intentionally
   compatible.
4. Ingest the exact native object into DataHub using a unique platform
   instance.
5. Resolve its URN from live search and prove a live lineage path.
6. Map the URN to exactly one native saved object.
7. Capture source object, immutable query identity, schedule set, content
   fingerprint, and recovery data.
8. Run content validation before mutation and record exact scope.
9. Create a plan for one allowlisted object with no wildcard target.
10. Bind authorization to instance, model, Explore, folder, object, source
    fingerprint, legacy field, and replacement field.
11. Reread source and targets immediately before apply.
12. Create or reuse the replacement query through the documented API and
    update only the approved saved object.
13. Compare actual target set and changed fields to the plan.
14. Run Content Validation and execute the migrated query safely.
15. Compare bounded result semantics defined before apply.
16. Exercise compensation and verify the original state.
17. Reapply and validate idempotency.
18. Apply the final intended state, refresh ingestion, and reconcile DataHub.
19. Attach the live receipt without closing unrelated consumers.

## Acceptance evidence

Required behavior:

- authenticated principal and effective permissions are recorded safely;
- DataHub discovers the exact live Looker consumer outside repository scope;
- identity mapping yields exactly one native object;
- plan target contains one allowlisted object;
- stale source, changed schedules, invalid replacement, expanded folder
  results, and missing permission all refuse before mutation;
- actual change contains only approved fields;
- Content Validation runs at the intended project and folder scope;
- migrated query executes or receives the predeclared strongest safe check;
- schedules, filters, calculations, alerts, and merged-result relevance are
  evaluated explicitly;
- compensation restores and verifies the original object;
- repeated apply is idempotent;
- live receipt is accepted and fixture receipt remains rejected;
- fresh DataHub evidence records the resulting edge state or an explicit
  connector limitation;
- unrelated opaque consumers continue to block the broader campaign.

Required commands:

```bash
make check
retirement-conductor adapter looker preflight --campaign <id>
retirement-conductor adapter looker plan --campaign <id>
retirement-conductor adapter looker apply --campaign <id>
retirement-conductor adapter looker validate --campaign <id>
retirement-conductor campaign reconcile --campaign <id>
retirement-conductor campaign evaluate --campaign <id>
git diff --check
```

Inspect:

- permission and identity evidence;
- before/after native object;
- exact plan and target comparison;
- native validation and query evidence;
- compensation result;
- live receipt;
- graph reconciliation;
- combined manifest.

## Stop or reframe conditions

- If exact native identity cannot be obtained, leave the consumer unresolved.
- If the only supported mutation is broader than the authorized disposable
  scope, do not apply it.
- If Content Validation and safe query checks cannot provide meaningful
  evidence, reframe Looker as owner-managed rather than auto-validated.
- If the second adapter shares no meaningful campaign semantics with Git/dbt,
  reassess the adapter-product thesis before adding more platforms.

## Risks changed

- R-02 identity mapping;
- R-03 semantic equivalence;
- R-06 partial mutation;
- R-08 adapter economics;
- R-11 platform capability drift;
- R-14 permissions;
- R-18 idempotency;
- R-19 validation side effects.
