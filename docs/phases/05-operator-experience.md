# Phase 05 — Operator experience

## Outcome

An operator who does not know DataHub or dbt can understand what is
being changed, what evidence was checked, what the system did, why it refused
or permitted retirement, and what exact action remains. Every view is rendered
from canonical campaign state.

## Dependencies

- phase 04 complete vertical and manifest;
- real refusal and all-closed fixture artifacts.

## Scope

In scope:

- plain-language command output;
- plan review and explicit apply confirmation;
- campaign inspect, explain, and resume commands;
- generated local HTML report;
- evidence coverage and blind-spot presentation;
- per-consumer state and native action detail;
- accessible, responsive rendering;
- exportable public-safe sample output.

Excluded:

- a separate policy or business-logic layer;
- hand-authored success data;
- account management;
- general dashboard builder;
- always-on server unless a real interaction requires one.

## Deliverables

- stable CLI command and output conventions;
- concise campaign summary;
- consumer inventory and blocker views;
- evidence-envelope view;
- before/after action and validation view;
- generated single-campaign HTML report;
- redaction boundary for public export;
- screenshots and browser validation from real generated artifacts;
- operator runbook for create, plan, apply, inspect, resume, and gate.

## Work breakdown

1. Interview the canonical manifest for every operator question; add no hidden
   UI-only state.
2. Make the first screen answer:
   - what is being retired;
   - what replaces it;
   - current decision;
   - consumer and blocker counts;
   - evidence coverage;
   - required next action.
3. Explain every refusal with stable code, plain language, evidence source, and
   safe recovery action.
4. Show native changes and validators without dumping sensitive logs.
5. Distinguish live, fixture, replay, missing, and stale evidence visually and
   textually.
6. Expose scope and limitations before the positive result.
7. Generate the report deterministically from the manifest.
8. Add keyboard navigation, focus behavior, semantic markup, contrast, and
   reduced-motion behavior.
9. Validate small and large screens.
10. Verify public export contains no private paths, principals, tokens, SQL
    text, or raw data.

## Acceptance evidence

Required behavior:

- a nontechnical reviewer can explain the target, replacement, action, result,
  and blocker from the first view;
- every displayed count and status traces to manifest fields;
- a stale receipt is unmistakable from a validated receipt;
- unknown coverage cannot look complete;
- plan and apply are separate, and apply shows exact authorized scope;
- the CLI and report show the same decision and digest;
- report generation is deterministic;
- public export passes secret and private-path scanning;
- keyboard-only operation reaches every interactive control;
- automated accessibility checks and real-browser smoke flows pass;
- narrow mobile layout remains usable.

Required commands:

```bash
make check
retirement-conductor campaign inspect --campaign <id>
retirement-conductor campaign explain --campaign <id>
retirement-conductor report build --campaign <id>
make test-ui
git diff --check
```

Inspect:

- CLI output for all four final decisions;
- report for live refusal and all-closed fixture;
- public export;
- accessibility report;
- desktop and mobile screenshots.

## Stop or reframe conditions

- If the interface requires duplicated policy logic, change the manifest or
  renderer rather than copying the engine.
- If a field cannot be explained without leaking sensitive evidence, redesign
  the safe summary.
- If visual polish begins to drive new unverified behavior, stop and return to
  engine artifacts.

## Risks changed

- R-09 report-versus-executor drift;
- R-13 integrity interpretation;
- R-15 sensitive evidence;
- R-26 blocked-campaign usability.
