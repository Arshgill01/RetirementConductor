# Pull request

## Product outcome

What complete behavior, phase acceptance item, or risk does this change
advance?

## Evidence

List commands run and artifacts inspected.

## Refusal behavior

Which negative, stale, partial, unauthorized, repeated, or interrupted cases
were exercised?

## Scope and blind spots

What does this change intentionally not support or prove?

## Checklist

- [ ] Contracts, decisions, risks, and phase state match observed behavior.
- [ ] No UI or report path reimplements policy.
- [ ] No live claim relies on fixture or replay evidence.
- [ ] No credentials or sensitive evidence are tracked.
- [ ] `make check` passes.
