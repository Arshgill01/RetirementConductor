# Phase 07 — Security and reliability

## Outcome

The DataHub plus Git/dbt product withstands adversarial inputs, interrupted
execution, least-privilege constraints, overlapping campaigns, source and
graph drift, partial failures, benchmark manipulation, and evidence tampering
without producing false readiness or exposing sensitive material.

## Dependencies

- phases 04 and 06 exercised with live disposable local systems;
- representative deployment configuration;
- stable refusal and event contracts.

## Scope

In scope:

- threat model and data-flow review;
- credential and capability separation;
- authorization binding;
- artifact classification, redaction, and retention;
- fault injection;
- retry and rate-limit behavior;
- local locking and overlapping campaigns;
- backup, restore, and database migration;
- receipt and event integrity;
- dependency and supply-chain review;
- operational observability.

Excluded:

- inventing enterprise identity infrastructure;
- broad production mutation;
- cryptographic signing without an operational key model;
- distributed control plane before a real deployment needs it.

## Deliverables

- threat model with assets, actors, trust boundaries, and abuse cases;
- least-privilege role guidance for every integration;
- plan/apply/validate/gate capability tests;
- redaction and retention policy;
- fault-injection suite;
- database backup, restore, and migration runbook;
- security scanning and dependency review;
- operational event and error metrics;
- recovery drills for every partial state;
- reviewed security section in operator documentation.

## Work breakdown

1. Enumerate credentials, evidence, source content, campaign state, and final
   action as separate assets.
2. Model malicious specifications, prompt content, adapters, source owners,
   and compromised credentials.
3. Bind every approval to exact campaign, plan, source, target, and principal.
4. Prove read-only and plan-only principals cannot apply.
5. Prove the general campaign principal cannot perform the producer action.
6. Inject secrets and sensitive SQL into source responses and verify safe
   storage and rendering.
7. Exercise 401, 403, 404, conflict, validation, rate-limit, timeout, and
   connection-loss behavior.
8. Interrupt before, during, and after native apply and compensation.
9. Corrupt event, receipt, artifact, and database material deliberately.
10. Run overlapping and replacement-chain campaigns.
11. Verify backup and restore preserve decisions and evidence references.
12. Review dependency licenses, vulnerabilities, update path, and provenance.
13. Define operational signals for stuck, repeatedly failing, or stale
    campaigns.
14. Exercise clock skew, policy and configuration drift, recreated native
    identities, and unknown apply outcomes.
15. Run hostile repository validators with path, symlink, subprocess,
    environment, secret, and network escape attempts.
16. Exercise the gate with unavailable local state, untrusted CI provenance,
    tampered artifacts, and failed DataHub read-back.
17. Attempt gate-result replay, a different producer plan, delayed action, and
    state change between check and action.
18. Start two runners against copied or unsupported shared state and prove the
    single-writer deployment refuses.

## Acceptance evidence

Required behavior:

- no credential appears in tracked files, logs, manifests, reports, or error
  messages;
- plan-only principal cannot apply;
- apply authorization for one target cannot affect another;
- source-supplied prompt text cannot change deterministic policy or command
  scope;
- malformed and tampered receipts refuse;
- every injected failure yields safe state and an actionable refusal;
- partial mutation either compensates or remains visibly unsafe;
- retries do not duplicate native changes;
- two campaigns cannot mutate the same native object concurrently;
- database backup and restore reproduce canonical manifests;
- state migration can roll forward safely;
- dependency and secret scans pass;
- no test produces false readiness.
- clock, replacement, policy, configuration, authorization, and identity drift
  all invalidate prior readiness;
- unknown native outcomes are reconciled before retry;
- hostile repository code cannot escape its declared validation boundary;
- the gate fails closed when state, provenance, or publication verification is
  unavailable.
- gate success is single-use and bound to the exact trusted producer
  invocation;
- two campaign writers cannot each establish authoritative readiness.

Required commands:

```bash
make check
make test-security
make test-faults
make test-recovery
make scan
git diff --check
```

Inspect:

- threat model;
- least-privilege receipts;
- failure matrix;
- recovery logs;
- backup and restored state digests;
- scan findings and dispositions.

## Stop or reframe conditions

- If source credentials cannot be scoped narrowly enough, keep that adapter
  plan-only or owner-managed.
- If a native operation cannot recover or expose a safe durable partial state,
  prohibit automated apply.
- If the final producer workflow cannot prevent bypass, narrow the claim to an
  advisory system until enforcement is real.

## Observed acceptance

Complete at tested commit `6e4ca87`. The post-removal security, fault, and
recovery suites passed 53, 47, and 40 tests; plan-only Git/dbt could not apply;
failure paths remained contained or refused; backup/restore reproduced the
canonical manifest and schema versions; copied state refused before database
change; and vulnerability, license, lock, secret, and public-artifact reviews
passed. The evidence binds to Phase 06's zero-false-readiness result. Public
evidence is in `artifacts/public/phase07/` with summary digest
`sha256:38ca5631665d6b3402b8b07226c49a3531490a6e3adcb95053d4e671c432cc23`.

## Risks changed

- R-06 partial mutation;
- R-07 concurrency;
- R-13 provenance;
- R-14 credentials;
- R-15 sensitive evidence;
- R-18 retries;
- R-19 side effects;
- R-20 gate bypass;
- R-23 recovery;
- R-25 source history;
- R-27 trusted time;
- R-28 untrusted execution;
- R-29 recreated identity;
- R-30 replacement drift;
- R-31 unknown mutation outcome;
- R-32 evidence granularity;
- R-33 executable-input drift;
- R-34 gate provenance and availability;
- R-35 gate-to-action race;
- R-36 divergent campaign writers;
- R-37 contradictory connector evidence.
