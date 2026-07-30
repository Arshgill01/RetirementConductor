# Phase 08 — Deployment and adoption proof

## Outcome

Another team can install, configure, evaluate, operate, upgrade, and remove
Retirement Conductor; at least one real operator workflow establishes whether
the product saves consequential work and earns continued use.

## Dependencies

- complete vertical and hardened runtime;
- public-safe disposable example;
- documented DataHub Core and optional Cloud boundaries;
- at least one prospective operator willing to evaluate a real workflow.

## Scope

In scope:

- reproducible package and container;
- local and CI installation;
- configuration and secret references;
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
- customer-observation notes without sensitive details;
- measured product-behavior and customer-value outcomes;
- maintenance, release, and contribution policy.

## Work breakdown

1. Install from the published artifact into a clean environment.
2. Configure DataHub and Git/dbt using secret references.
3. Run preflight and make every missing capability actionable.
4. Execute the public-safe campaign end to end.
5. Verify backup, upgrade, rollback, and removal.
6. Document exact Core behavior and optional Cloud improvements separately.
7. Observe a real operator performing a recent retirement or replacement.
8. Measure inventory expansion, native identities resolved, interventions,
   validation outcomes, late consumers, and gate results.
9. Compare the workflow with the team's previous process.
10. Record rejection reasons and operational burden.
11. Update product scope, risks, and competitive boundary from evidence.
12. Publish only artifacts another team can reproduce safely.

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
- an independent operator can complete the runbook;
- observed workflow evidence addresses frequency, value, friction, and buyer;
- the product is reframed if real use contradicts the current thesis;
- release artifacts, repository state, and documentation agree.

Required commands:

```bash
make check
make package
make test-install
make test-upgrade
make test-reference-campaign
git diff --check
```

Inspect:

- built package and optional image;
- clean-environment logs;
- compatibility evidence;
- backup and upgrade artifacts;
- independent operator notes;
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

## Risks changed

- R-08 adapter economics;
- R-11 edition portability;
- R-14 deployment credentials;
- R-21 adoption frequency;
- R-22 competitive convergence;
- R-23 operational recovery;
- R-26 long-running blocked campaigns.
