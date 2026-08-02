# Phase 08 — Deployment proof and adoption boundary

## Outcome

The release can be installed, configured, evaluated, operated, upgraded, and
removed from clean environments. The independent-operator protocol remains a
clearly separated follow-on boundary: until a real observation exists, the
product makes no customer-value, adoption, or buyer claim.

## Dependencies

- complete vertical and hardened runtime;
- public-safe disposable example;
- documented DataHub Core and optional Cloud boundaries;
- an explicit non-claim when no prospective operator is available.

## Scope

In scope:

- reproducible package and container;
- local and CI installation;
- configuration and secret references;
- explicit single-writer deployment identity and state-directory ownership;
- health and preflight diagnostics;
- DataHub Core compatibility and optional Cloud integration;
- upgrade and rollback path;
- backup and removal;
- evaluation guide using safe data;
- real operator observation and product metrics;
- maintenance and contribution process.

Excluded:

- infrastructure choices unsupported by an actual adopter;
- always-on hosted service before deployment evidence requires it;
- broad connector count as an adoption proxy;
- treating repository stars or page views as product value.

## Deliverables

- versioned Python package;
- minimal container image if justified by the operator flow;
- install, configure, upgrade, backup, restore, and uninstall documentation;
- environment and integration preflight;
- one safe reference campaign that runs from a clean machine;
- compatibility matrix with executed evidence;
- operator evaluation guide;
- telemetry that is local and opt-in by default;
- a no-secret independent-operator protocol and observation template;
- an explicit `NOT_RUN` artifact when customer-value evidence is absent;
- maintenance, release, and contribution policy.

## Work breakdown

1. Install from the published artifact into a clean environment.
2. Configure DataHub and Git/dbt using secret references.
3. Run preflight and make every missing capability actionable.
4. Execute the public-safe campaign end to end.
5. Verify backup, upgrade, rollback, and removal.
6. Document exact Core behavior and optional Cloud improvements separately.
7. Prepare the protocol for a real operator performing a recent retirement or
   replacement without manufacturing an observation.
8. If an independent operator becomes available, measure inventory expansion,
   native identities resolved, interventions, validation outcomes, late
   consumers, and gate results.
9. If observed, compare the workflow with the team's previous process.
10. Preserve `NOT_RUN` plus the exact remaining boundary otherwise.
11. Update product scope, risks, and competitive boundary from evidence.
12. Publish only artifacts another team can reproduce safely.
13. Prove a second runner or copied state receives an actionable unsupported
    deployment refusal.

## Acceptance evidence

Required behavior:

- clean installation succeeds using documented commands;
- configuration errors identify the missing variable, capability, or
  permission without exposing secrets;
- safe reference campaign reproduces its expected decisions and digests;
- Core-only operation completes the supported path;
- Cloud-only enhancements are optional and labeled;
- upgrade preserves campaigns and rollback restores the prior working version;
- uninstall removes product state only after explicit operator confirmation;
- absent independent operation remains `NOT_RUN` and produces no value claim;
- the product is reframed if real use contradicts the current thesis;
- release artifacts, repository state, and documentation agree;
- single-writer requirements are explicit, diagnosed by preflight, and refuse
  unsupported multi-writer operation.

Required commands:

```bash
make check
make package
make test-install
make test-upgrade
make test-reference-campaign
make phase08-evidence
git diff --check
```

Inspect:

- built package and optional image;
- clean-environment logs;
- compatibility evidence;
- backup and upgrade artifacts;
- independent operator boundary or genuine observation notes;
- updated success measures and risk register.

## Stop or reframe conditions

- If an independent team cannot operate the product without its authors,
  simplify the runtime and configuration.
- If installation and maintenance outweigh the recurring coordination value,
  explore a DataHub-embedded or CI-only shape.
- If real operators use the system only as an impact report and bypass native
  execution, revisit the product boundary.
- If usage frequency and willingness to adopt are insufficient, preserve the
  protocol as a focused tool or runbook rather than adding breadth.

## Follow-on adoption evidence

An independent operator observation remains required before satisfying
RC-018 or claiming recurring customer value. It must address frequency,
baseline and observed work, author intervention, friction, decision-changing
value, willingness to adopt or reject, and buyer or approver role. Under the
controlling `GOAL.md`, absence of that human does not block the credential-
independent engineering completion, but it must remain visible and must never
be simulated.

## Observed engineering acceptance

Complete at tested commit `c3440b2`. The 0.2.0 wheel and source archive
reproduced byte-for-byte, contained no deprecated adapter surface, and used a
hash-bound runtime lock. Clean installs under Python 3.11, 3.12, 3.13, and
3.14 reproduced the blocked fixture and actionable preflight; confirmed state
and package removal passed. Upgrade from 0.1.0 preserved the campaign through
schema versions 1 to 3, and backup-based rollback restored the prior pair.

The clean installed wheel performed 35 product operations against loopback
DataHub Core v1.6.0 and MCP v0.6.0 at the pinned commit. Native dbt passed; the
isolated campaign reached `READY_TO_RETIRE` with one sentinel; a late consumer
reopened it; and the 41-consumer rich graph remained `UNSAFE`. Public evidence
is in `artifacts/public/phase08/` with engineering-acceptance digest
`sha256:c7b6b754380f3c01c411db7b847959e02bea2f8bfe0f8856bb144a4db5876d05`.
RC-018 remains explicitly `NOT_RUN`.

## Risks changed

- R-08 adapter economics;
- R-11 edition portability;
- R-14 deployment credentials;
- R-21 adoption frequency;
- R-22 competitive convergence;
- R-23 operational recovery;
- R-26 long-running blocked campaigns;
- R-36 divergent campaign writers.
