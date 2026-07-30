# Phase 00 — Foundation and evidence promotion

## Outcome

A small executable Python repository exists with versioned product contracts,
a validated retirement specification, deterministic campaign fixtures, and
the proven safety behavior promoted from the preceding experiment without
copying experiment-specific machinery.

## Dependencies

None. The controlling inputs are:

- [Product definition](../PRODUCT.md)
- [Core contracts](../CONTRACTS.md)
- [Evidence baseline](../EVIDENCE_BASELINE.md)
- [Decision log](../DECISIONS.md)

## Scope

In scope:

- Python package and command-line entry point;
- executable schemas for specification, evidence envelope, consumer receipt,
  and campaign manifest;
- canonical JSON and digest utilities;
- stable domain vocabulary and refusal codes;
- content-hash precondition behavior;
- deterministic disposable fixtures;
- test, lint, format, type, secret, and documentation checks;
- public-safe promotion of the minimum prior evidence.

Excluded:

- live DataHub calls;
- live repository mutation;
- live Looker calls;
- network service, task queue, or distributed state;
- web application.

## Deliverables

- `pyproject.toml` with the minimum supported Python version and justified
  dependencies;
- `src/retirement_conductor/` package;
- `tests/` split between unit, contract, and fixture behavior;
- `schemas/` with versioned JSON Schemas;
- `fixtures/` with one compatible replacement and multiple refusal cases;
- `artifacts/public/` containing only reviewed, public-safe evidence;
- `retirement-conductor validate-spec` command;
- `retirement-conductor fixture run` command;
- repository checks invoked by `make check`;
- updated evidence, risks, and decisions.

## Work breakdown

1. Inventory the prior experiment by commit and copy no files blindly.
2. Promote canonical JSON and hashing with independent tests.
3. Define typed campaign, consumer, source, disposition, and decision values.
4. Turn the contracts in `docs/CONTRACTS.md` into strict schemas.
5. Validate that unknown and extra fields are handled intentionally.
6. Implement specification parsing without resolving credentials.
7. Implement scoped path resolution and content-hash preconditions.
8. Build fixtures for:
   - compatible field replacement;
   - identical target and replacement;
   - stale source;
   - invalid replacement;
   - unauthorized path;
   - incomplete evidence source;
   - ambiguous identity.
9. Generate deterministic fixture artifacts and verify reruns.
10. Add repository validation and public-safe artifact review.

## Acceptance evidence

Required behavior:

- valid specification normalizes to canonical JSON;
- malformed, ambiguous, and unsupported specifications refuse with stable
  codes;
- identical fixture runs produce identical digests;
- changing source content produces `SOURCE_` refusal before mutation;
- an outside-root path produces `SCOPE_` refusal;
- fixture mode is unambiguous and cannot satisfy a live-evidence policy;
- schemas reject missing required fields and unrecognized critical fields;
- no credentials or private artifacts are tracked.

Required commands:

```bash
make check
pytest
retirement-conductor validate-spec fixtures/specs/valid.yaml
retirement-conductor fixture run fixtures/specs/valid.yaml
git diff --check
```

Inspect:

- normalized specification;
- fixture event log;
- generated receipt and manifest;
- refusal output for every negative fixture;
- dependency list and license compatibility.

## Stop or reframe conditions

- If strict schemas cannot represent the proven experiment without
  source-specific fields leaking into the campaign core, revise the contract
  before implementation.
- If the promoted code requires the entire experiment harness, extract the
  invariant behavior again rather than importing the harness.
- If deterministic rebuilds require hidden time or environment input, fix the
  contract instead of tolerating unstable receipts.

## Risks changed

- R-05 stale source;
- R-09 report-versus-executor drift;
- R-13 integrity versus authorship;
- R-14 secret exposure;
- R-23 resumability groundwork;
- R-24 overbroad generated changes.
