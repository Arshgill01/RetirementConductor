# Operator runbook

This runbook operates one campaign from the canonical SQLite state and
manifest. Terminal summaries, explanations, HTML reports, DataHub
publication, and the producer gate all consume that same state; none of these
views recomputes policy.

The examples use non-secret local paths. Supply credentials only through the
source-specific runtime references documented by its adapter. Never paste
tokens, private query text, or sensitive result data into a specification,
manifest, report, or shell history.

## Establish one campaign context

Choose one deployment writer and keep the same store and artifact directory
for the campaign:

```bash
export RC_CAMPAIGN=ret-orders-git-dbt
export RC_STORE=.retirement-conductor/campaigns.sqlite
export RC_WRITER=local-operator
export RC_ARTIFACTS=.retirement-conductor/artifacts
```

Create a campaign with a trusted RFC 3339 event time:

```bash
retirement-conductor campaign create \
  fixtures/specs/git-dbt-live.yaml \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER" \
  --occurred-at 2026-07-30T10:00:00Z
```

Use a current trusted time; the example timestamp is not reusable
authorization.

## Inspect before acting

The concise view answers what changes, the current decision, consumer and
condition counts, evidence coverage, the next action, and the canonical
manifest digest:

```bash
retirement-conductor campaign inspect \
  --campaign "$RC_CAMPAIGN" \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER" \
  --artifact-dir "$RC_ARTIFACTS"
```

Use the expanded explanation to inspect source scope, freshness, pagination,
limitations, each consumer receipt state, stable condition codes, evidence
sources, and safe recovery actions:

```bash
retirement-conductor campaign explain \
  --campaign "$RC_CAMPAIGN" \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER" \
  --artifact-dir "$RC_ARTIFACTS"
```

`COMPLETE` always means complete only within the displayed envelope. An empty
inventory or absent query history is never presented as proof that no
consumer exists. `STALE`, `MISSING`, and `VALIDATED` receipts remain distinct.

## Review the plan and confirm the exact digest

Preflight and planning are read-only:

```bash
retirement-conductor adapter git-dbt preflight \
  --campaign "$RC_CAMPAIGN"

retirement-conductor adapter git-dbt plan \
  --campaign "$RC_CAMPAIGN"
```

Inspect the exact native identity, source commit, file allowlist,
before/after fingerprints, validators, rollback boundary, and plan digest.
After review, copy the displayed digest exactly:

```bash
export RC_PLAN_DIGEST='<exact-plan-digest-from-reviewed-plan>'
```

Authorization and interactive confirmation are independent requirements.
Authorize the same plan with bounded authority and expiry, then pass the
reviewed digest to apply:

```bash
retirement-conductor adapter git-dbt authorize \
  --campaign "$RC_CAMPAIGN" \
  --authorized-at 2026-07-30T10:05:00Z \
  --expires-at 2026-07-30T11:05:00Z

retirement-conductor adapter git-dbt apply \
  --campaign "$RC_CAMPAIGN" \
  --confirm-plan-digest "$RC_PLAN_DIGEST"
```

Missing confirmation refuses with `AUTH_APPROVAL_MISSING`; a digest other
than the current authorized plan refuses with `AUTH_APPROVAL_WRONG_PLAN`.
Confirmation never expands the plan's target set or replaces its source
preconditions.

Run the source-native validator and inspect its receipt:

```bash
retirement-conductor adapter git-dbt validate \
  --campaign "$RC_CAMPAIGN"

retirement-conductor campaign evaluate \
  --campaign "$RC_CAMPAIGN"
```

## Resume an interrupted campaign

Replay and inspect current state before choosing a recovery transition. Resume
requires a fresh idempotency key and trusted time:

```bash
retirement-conductor campaign resume \
  --campaign "$RC_CAMPAIGN" \
  --state MIGRATING \
  --occurred-at 2026-07-30T10:30:00Z \
  --idempotency-key resume-after-native-reread \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER" \
  --artifact-dir "$RC_ARTIFACTS"
```

Use only the legal state that matches the observed recovery point:
`INVENTORIED`, `MIGRATING`, or `RECONCILING`. A timed-out apply is
`OUTCOME_UNKNOWN`; reread the native object before resuming or retrying.

## Build a local or public-safe report

The local report preserves the identities required for operation:

```bash
retirement-conductor report build \
  --campaign "$RC_CAMPAIGN" \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER" \
  --artifact-dir "$RC_ARTIFACTS" \
  --output .retirement-conductor/reports/campaign.html
```

For a reviewable sample outside the operating boundary, request structural
redaction:

```bash
retirement-conductor report build \
  --campaign "$RC_CAMPAIGN" \
  --store "$RC_STORE" \
  --writer-id "$RC_WRITER" \
  --artifact-dir "$RC_ARTIFACTS" \
  --output .retirement-conductor/reports/campaign-public.html \
  --public
```

Public mode removes campaign, field, consumer, source, principal, version,
limitation, and history identities while retaining the decision, canonical
manifest digest, counts, evidence status, and recovery shape. The private
canonical manifest remains the integrity authority. Run the repository secret
and public-artifact scans before publishing any generated sample.

## Reconcile and gate

Follow the
[reconciliation and producer gate runbook](RECONCILIATION_GATE.md) to refresh
equivalent evidence, publish and verify the DataHub summary, issue one
manifest-bound producer plan, and invoke the gate.

The producer action is permitted only when the current canonical decision is
`READY_TO_RETIRE` and every bound source, publication, authorization,
validator, provenance, and freshness check still passes. A previously green
report or digest is not reusable authorization.

## Acceptance inspection

Run:

```bash
make phase05-browser
make phase05-evidence
make test-ui
make check
git diff --check
```

Inspect all four CLI decisions, the live refusal report, the all-closed fixture
report, the public export, both responsive screenshots, keyboard focus order,
disclosure activation, and both axe results. Fixture output must remain
visibly fixture-bounded and cannot satisfy a live-evidence policy.
