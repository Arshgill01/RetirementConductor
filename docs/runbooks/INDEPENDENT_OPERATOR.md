# Independent operator session

This runbook turns the remaining human boundary into a controlled evaluation.
It does not turn an author-operated demo into independent evidence.

## Who qualifies

Use one data, analytics, platform, governance, or ML infrastructure practitioner
who did not implement Retirement Conductor. Prefer someone who has recently
renamed, deprecated, or removed a field. Record only a role and team category;
do not publish a name or employer.

The participant operates disposable resources. The author may make the packet
and services available, then observes silently. Every hint, command, repair, or
interpretation supplied by the author is an intervention and must be recorded.

## Two valid session depths

The **core-workflow observation** takes about 30–45 minutes. It tests whether a
fresh practitioner can understand the product, inspect a campaign, explain the
evidence boundary, and correctly handle readiness reversal and gate refusal.
It is useful independent usability evidence, but it does not by itself satisfy
the full RC-018 deployment/adoption requirement.

The **full RC-018 observation** includes clean installation, deployment
preflight, reference operation, backup, upgrade or rollback, and planned
removal. Reserve 60–90 minutes. Only this track can satisfy RC-018, and only if
the value/buyer observations in [Evaluation](../EVALUATION.md) are also real.

## Author setup

Run:

```bash
make operator-packet
```

The command builds the release and creates an ignored, checksum-bound directory
under `.retirement-conductor/operator-evaluation/`. Give that directory and
disposable service endpoints to the participant. Do not give unpublished
commands or the expected answer.

If credentials are required, provide short-lived secret references outside the
packet. Never paste secrets into notes, screenshots, shell history, or Git.

## Participant brief

The participant receives this outcome, not a click-by-click script:

> Decide whether the declared legacy field may be retired. Use the packaged
> product and published documentation. Inspect the evidence scope, complete only
> authorized changes, validate in native systems, reconcile fresh evidence, and
> determine whether the producer action is permitted. When a late consumer is
> introduced, determine what changed and whether any previous permission remains
> usable.

For the core-workflow track, the author may pre-start disposable DataHub and
source services. For the full track, follow [Evaluation](../EVALUATION.md) and
the [Deployment runbook](DEPLOYMENT.md).

## Observation rules

- Start the timer when the participant opens `START_HERE.md`.
- Screen recording is optional; written timestamps and canonical artifact IDs
  are sufficient.
- Record every author intervention verbatim and when it occurred.
- Let refusals stand. Do not repair the run invisibly.
- Ask the participant to narrate why a decision is safe, blocked, or unsafe.
- After the run, ask the participant whether the evidence changed a decision,
  whether they would use it again, and what would prevent adoption.
- Keep raw notes outside Git. Commit only a redacted record reviewed by the
  participant for meaning.

## Acceptance

A core-workflow observation passes only if the participant, without an
undocumented command supplied by the author:

1. identifies DataHub as bounded cross-system context rather than universal
   proof;
2. finds the exact native consumer identities and validator results;
3. distinguishes a campaign decision from authorization;
4. explains why a late consumer reverses readiness;
5. confirms that the prior Retirement Lease is invalidated and the producer
   action is refused;
6. identifies at least one concrete trust gap or operational cost.

Report failure honestly. A failed independent run is high-value product
evidence; coaching it into a pass destroys the evidence.
