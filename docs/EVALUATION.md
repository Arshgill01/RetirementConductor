# Independent operator evaluation

Phase 08 requires a real operator to establish whether Retirement Conductor is
operable without its authors and whether a recurring field-replacement
workflow creates consequential value. A fixture, scripted author run, survey
response, or polished report cannot satisfy that requirement.

Use a recent real workflow, a prospective operator, and disposable or
otherwise explicitly safe resources. Never mutate production data, shared BI
content, or a producer schema during evaluation.

## Before the session

Record a redacted baseline:

- operator role and team category, without a name or employer;
- how often the team replaces or retires fields;
- elapsed time, manual steps, handoffs, and native validators in the most
  recent comparable workflow;
- where consumers were missed, rediscovered, or escalated;
- the person or role that can approve adoption and budget;
- the exact disposable DataHub and Git/dbt scope plus dataset revision and
  synthetic scenario identifier.

Prepare a reviewed wheel, hash-locked requirements, release checksums, the
[deployment runbook](runbooks/DEPLOYMENT.md), and an ignored local
configuration. The author may set up the disposable services before the
clock starts but may not silently operate the product for the participant.

## Operator task

Ask the operator to complete these tasks from the documentation:

1. verify and install the release in a clean environment;
2. configure the single-writer state and secret references;
3. run deployment and source preflights;
4. run the built-in fixture and explain why it remains blocked;
5. execute the disposable reference campaign;
6. identify inventory expansion, exact native identities, interventions,
   validator outcomes, late consumers, and gate decisions;
7. create and verify a backup;
8. inspect an upgrade or rollback rehearsal;
9. generate a removal plan, explain its confirmation boundary, and remove only
   disposable state when authorized.

The participant should use the runbook without an unpublished command list.
Record every author intervention and the point at which it occurred. A run
completed through step-by-step author operation is useful friction evidence
but is not an independent pass.

## Product-behavior observations

Capture counts and outcomes from the canonical artifacts, not memory:

- repository-only and DataHub-expanded consumer counts;
- native identities resolved, ambiguous, or unresolved;
- planned, applied, validated, compensated, or untouched consumers;
- native validator commands and pass/fail/refusal outcomes;
- late consumers and source freshness or pagination limitations;
- ready, unsafe, blocked, and review-required decisions;
- producer gate actions and refusals;
- clean-install, preflight, reference, backup, and removal elapsed time;
- actionable versus unexplained refusal messages;
- author interventions and documentation defects.

Do not include raw SQL, dashboard content, principal names, tokens, private
paths, source data, or screenshots that reveal them.

## Customer-value observations

Compare the observed run with the recorded baseline:

- prior and current elapsed time;
- prior and current manual steps and handoffs;
- work avoided, added, or merely shifted;
- whether the evidence changed a real decision;
- expected recurrence over a month, quarter, and year;
- willingness to run it again without the author;
- willingness to adopt, reject, or fund it;
- buyer or approver role;
- operational burden, trust gaps, and rejection reasons.

Do not infer value from feature count, repository activity, or a successful
fixture. If the team performs the workflow too rarely, uses the product only
as an impact report, bypasses native execution, cannot operate it without its
authors, or finds maintenance greater than recurring value, record that
directly and apply the phase stop-or-reframe conditions.

## Acceptance interpretation

An independent result requires:

- a real prospective operator, not the implementation author;
- a recent or active workflow with a credible baseline;
- no author intervention needed to discover undocumented commands or repair
  product defects;
- safe completion of the documented operation;
- observed frequency, friction, value, willingness, and buyer evidence;
- a redacted record reviewed against the raw notes;
- explicit limitations and non-claims.

One operator cannot establish broad market demand. It can satisfy the bounded
operability observation and provide direct adoption evidence for the named
workflow. Contradictory evidence triggers a reframe; it must not be hidden by
adding connectors or weakening acceptance.

Use [the observation template](templates/OPERATOR_OBSERVATION.md). Keep raw
notes outside Git in access-controlled storage and commit only the
public-safe, inspected observation. The unresolved human boundary and
no-secret request format are maintained in [Access requirements](ACCESS.md).
