# Autonomous implementation goal

This file is the controlling execution contract for building Retirement
Conductor. It turns the product definition and phase documents into one
continuous assignment. An implementation run must not stop after producing a
plan, package skeleton, isolated feature, generated report, or partial
integration.

## Exact objective

> Implement Retirement Conductor end to end in this repository, satisfy every
> phase acceptance contract with inspectable evidence, and deliver the
> complete verified field-replacement workflow or an evidence-backed reframe.
> Finish every safe credential-independent task before reporting an external
> access blocker, and never manufacture live evidence.

## Current truth

The repository begins as a researched product and engineering specification,
not as an implemented product. The preceding experiment proved that DataHub
can materially expand the consumer inventory and that one dbt consumer can be
changed and validated safely. It did not prove durable product operation, a
live Looker path, a real producer gate, or adoption by another operator.

The implementation must preserve that distinction:

- prior experiment evidence is a baseline, not phase-completion evidence;
- fixture, replay, and fake-server results are useful tests but are not live
  integration results;
- a polished interface does not compensate for an incomplete control loop;
- refusal is valid product output, but inability to execute the supported
  path is not success.

## Instruction order

Read these files completely before a non-trivial change:

1. `AGENTS.md`
2. this file
3. `STATUS.md`
4. `README.md`
5. `docs/PRODUCT.md`
6. `PLAN.md`
7. the active file in `docs/phases/`
8. `docs/REQUIREMENTS_TRACEABILITY.md`
9. relevant sections of `docs/ARCHITECTURE.md`,
   `docs/CONTRACTS.md`, `docs/RISKS.md`, `docs/DECISIONS.md`,
   `docs/ACCESS.md`, and `docs/EVIDENCE_LEDGER.md`

If instructions conflict, preserve safety and truth first, then follow this
file, the product definition, the contracts, the phase acceptance contract,
and implementation convenience in that order. Record a consequential
resolution in `docs/DECISIONS.md`.

## Authority and repository boundary

The implementation run is authorized to:

- create and modify files in this repository;
- inspect the preceding experiment repository without modifying it;
- install ordinary local development dependencies needed by the documented
  implementation;
- start disposable local services and containers;
- create disposable repositories, databases, schemas, and fixtures;
- use configured credentials only against explicitly designated disposable
  resources;
- run tests, scanners, package builds, browser checks, and fault injection;
- make focused commits on the current branch and push those commits to
  `origin`.

The run is not authorized to:

- mutate production data, production BI content, or shared company assets;
- broaden a credential, permission, native target, or repository path;
- expose secrets or sensitive evidence in Git, logs, manifests, screenshots,
  reports, or chat;
- force-push, discard user changes, rewrite published history, or merge an
  unrelated branch;
- perform the final destructive producer action;
- silently weaken an acceptance condition to obtain a positive result.

Use the existing public repository and its current branch. Preserve unrelated
user changes. Commit coherent, verified milestones and push them after the
corresponding evidence and control documents agree.

## Required product outcome

The run must deliver one working vertical:

```text
declare one exact legacy field and compatible replacement
  → resolve both identities from live DataHub
  → inventory consumers through a declared evidence envelope
  → freeze identities, scope, source versions, and authorization
  → change one exact Git/dbt consumer on a reviewable branch
  → validate it with dbt-native commands
  → refresh and inventory through DataHub again
  → reopen on new, stale, partial, or changed evidence
  → publish and read back a stable DataHub campaign summary
  → permit or refuse the producer action through the same deterministic policy
```

It must also deliver one live bounded Looker saved-content path through the
same campaign and receipt semantics. The Looker path proves heterogeneous
execution; it must not become a separate migration utility with a copied
policy.

The command line, generated report, DataHub summary, and producer gate must
consume the same canonical manifest. No surface may recompute readiness.

## Phase authority

Each phase file is an acceptance contract:

1. [Phase 00 — foundation](docs/phases/00-foundation.md)
2. [Phase 01 — campaign kernel](docs/phases/01-campaign-kernel.md)
3. [Phase 02 — DataHub evidence](docs/phases/02-datahub-evidence.md)
4. [Phase 03 — Git and dbt execution](docs/phases/03-git-dbt-execution.md)
5. [Phase 04 — reconciliation and gate](docs/phases/04-reconciliation-gate.md)
6. [Phase 05 — operator experience](docs/phases/05-operator-experience.md)
7. [Phase 06 — Looker adapter](docs/phases/06-looker-adapter.md)
8. [Phase 07 — security and reliability](docs/phases/07-security-reliability.md)
9. [Phase 08 — deployment and adoption](docs/phases/08-deployment-adoption.md)

## Continuous execution protocol

Work through phases 00 through 08 in proof-dependency order. For each phase:

1. Read the whole phase file and its named risks.
2. Reconcile its deliverables with the requirements traceability matrix.
3. Implement the smallest complete behavior, including refusal paths.
4. Run focused checks while working.
5. Implement and run every acceptance command listed by the phase. A missing
   command is unfinished work, not a reason to skip its acceptance.
6. Inspect the artifacts, diffs, logs, and negative outcomes rather than
   trusting process exit status.
7. Record live, fixture, and replay modes accurately in the evidence ledger.
8. Update risks and decisions from observed results.
9. Update `STATUS.md` only after evidence exists.
10. Commit and push the verified milestone.
11. Continue immediately into the next available work.

Do not stop merely because:

- phase 00 or the campaign kernel passes;
- the DataHub graph can be queried;
- one migration receipt exists;
- a report looks complete;
- the all-closed fixture yields `READY_TO_RETIRE`;
- a live representative campaign correctly refuses;
- one external integration is awaiting access;
- the package builds or the current test suite passes.

Phase acceptance is cumulative. Later changes that invalidate earlier
evidence reopen the affected phase.

## Work available before external access

Missing external access must not serialize the entire build. Before requesting
user action, complete all safe work that does not require that boundary:

- phases 00 and 01 in full;
- a disposable local DataHub Core environment and phase 02 Core behavior;
- a disposable Git/dbt repository and phases 03 through 05;
- the Looker adapter, fake boundary, fixtures, preflight, access diagnostics,
  safety checks, and dry-run path that can be proven without a live instance;
- security, fault, recovery, packaging, install, upgrade, and reference
  campaign work that does not depend on live Looker;
- an exact generated access request containing only unresolved values and the
  next safe command.

After Looker access is present, finish the live phase 06 path and every
Looker-specific phase 07 check. After a prospective operator is available,
finish the independent operation and value evidence in phase 08.

An access-dependent phase can be partially implemented but cannot be marked
complete from a simulator. Record the split explicitly in `STATUS.md`.

## Evidence contract

Every material claim must be classified as one of:

- `live`: observed against the named running source;
- `fixture`: produced by deterministic controlled test data;
- `replay`: reproduced from a previously captured artifact;
- `analysis`: a reasoned conclusion that does not assert runtime behavior.

Every accepted phase result records:

- repository commit;
- exact command or operator action;
- source and tool versions;
- evidence mode;
- safe artifact path and digest;
- result and refusal code where applicable;
- what the result proves;
- limitations and unavailable scope.

Generated evidence that may contain credentials, raw SQL, private paths,
principal names, or source content stays outside Git. The tracked ledger may
contain only a redacted claim and digest.

No phase may use:

- a fixture receipt to satisfy a live policy;
- a disappearing graph edge as proof of closure;
- an owner acknowledgment as native validation;
- an empty result as proof of absence;
- a digest as proof of authorship;
- a successful API response as proof that the changed consumer works.

## Failure-closed requirements

The implementation must refuse promotion on every material unknown,
including:

- incomplete pagination or incomparable graph snapshots;
- missing, ambiguous, recycled, or changed native identity;
- table-level lineage presented as field-level certainty;
- source, replacement, policy, configuration, approval, or target drift;
- untrusted repository code escaping its execution boundary;
- target expansion, path traversal, symlink escape, or branch movement;
- timeout after a mutation whose result is unknown;
- partial apply or failed compensation;
- stale receipt, untrusted clock, or expired evidence;
- local campaign-store or publication-integrity failure at gate time;
- gate invocation from an untrusted artifact or bypassable producer path;
- replayed gate success, a gate-to-action race, or two independent campaign
  writers;
- late consumer appearance or source disappearance;
- missing required permission or evidence source.

Retries must distinguish “known not applied” from “outcome unknown.” An
unknown mutation outcome requires native reread and reconciliation before any
retry.

## Scope control

Do not broaden the product until the complete first vertical works. In
particular, do not introduce:

- a general connector framework before two live adapters expose shared needs;
- a network service, queue, distributed lock, or generic storage layer without
  observed deployment pressure;
- additional asset categories;
- a second policy implementation;
- a model-authorized state transition;
- a visual-only source of campaign truth.

If an existing native tool can perform mutation or validation safely, invoke
it behind the bounded adapter rather than rebuilding it.

## External boundary protocol

Use [Access requirements](docs/ACCESS.md) as the exact access contract.

When a boundary is missing:

1. prove that it is unavailable through safe preflight;
2. finish all other executable work;
3. identify the smallest disposable resource and least privilege needed;
4. generate a no-secret request with exact variable names, permissions, object
   scope, and verification command;
5. record the blocker and completed independent work in `STATUS.md`;
6. preserve a deterministic resume point;
7. continue any remaining independent phase work.

Never request credentials in chat. Ask the user to place them in the ignored
local configuration identified by the access document.

## Reframe protocol

Stop expanding implementation and record a reframe when observed evidence
invalidates a central thesis, including:

- DataHub does not add consequential cross-system context;
- exact native identity cannot be established safely;
- native validators cannot support a meaningful completion claim;
- the producer workflow cannot enforce refusal;
- Git/dbt and Looker share no useful campaign semantics;
- the workflow is not repeatable or valuable for a real operator.

A reframe requires:

- the exact failed experiment and evidence mode;
- observed result and limitations;
- affected requirement, decision, and risk IDs;
- the narrower product claim that remains defensible;
- code and documentation aligned with that claim.

Do not conceal invalidating evidence by adding platforms or presentation.

## Completion states

The execution objective has only three honest terminal states.

### Complete

Use only when:

- every requirement in the traceability matrix has direct evidence;
- phases 00 through 08 meet their acceptance contracts;
- the Git/dbt and Looker paths have live evidence;
- one live isolated all-closed campaign reaches `READY_TO_RETIRE`, while one
  live rich-graph campaign refuses on consequential unresolved consumers;
- a clean installation reproduces the reference campaign;
- the producer gate is actually enforceable and fails closed;
- an independent operator result is recorded;
- all repository and phase checks pass at the final commit;
- status, evidence, risks, decisions, docs, and implementation agree;
- the final commits are pushed and the remote commit is verified.

### Reframed

Use only when a central claim failed under the reframe protocol and the
repository now honestly implements and describes the narrower result.

### Externally blocked

Use only when the same concrete external boundary remains unavailable after
safe preflight and all credential-independent work is finished. The handoff
must include:

- the exact missing access or human evaluation;
- evidence that the boundary was reached;
- all work completed without it;
- the ignored destination for any secret;
- least-privilege scope;
- one verification command;
- one exact resume command;
- the remaining acceptance rows that cannot yet pass.

An implementation defect, failing test, difficult integration, or incomplete
phase is not an external blocker.

## Final handoff

The final report must state:

- terminal state and final commit;
- product behavior that works;
- live systems actually exercised;
- phase and requirement evidence;
- successful and refusal commands run;
- public artifacts and operator views;
- remaining limitations, residual risks, and external boundaries;
- remote push verification.

Do not use confidence language where direct evidence is available. State what
ran, what passed, what refused, and what remains unproven.
