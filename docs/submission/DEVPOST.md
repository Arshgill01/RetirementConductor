# Retirement Conductor — Devpost story

## Elevator pitch

**Replace a legacy data field without breaking the systems that still use it.**

Retirement Conductor uses DataHub to find consumers across the data stack,
migrates and tests the consumers it is authorized to change, then freshly
checks the world before it removes — or refuses to remove — the old field.

## Short description

Removing a warehouse column is rarely just a database change. The same field
may still feed dbt models, dashboards, Spark jobs, notebooks, reports, or AI
workflows owned by different teams.

Retirement Conductor turns that change into one evidence-backed campaign. It
uses DataHub as the cross-system dependency map, Codex as the operator,
source-native tools as the validators, and deterministic policy as the final
authority. A late consumer changes the answer from ready to unsafe, and the
producer action stops.

## Inspiration

Data teams accumulate legacy fields because removing them is riskier than
adding their replacements. Repository search is incomplete, catalog impact
analysis stops at a list, and a ticket approval can become stale before the
schema change runs.

We wanted to answer a harder operational question:

> Can we move every known consumer, prove the changed systems still work, and
> make the final database action obey the latest evidence?

## What it does

For one legacy field and one compatible replacement, Retirement Conductor:

1. resolves the exact fields and inventories downstream consumers in DataHub;
2. records the scope, freshness, pagination, permissions, and blind spots of
   the evidence;
3. maps supported consumers to exact native identities;
4. creates a reviewable Git/dbt migration after external human approval;
5. runs dbt-native parsing, builds, tests, and semantic checks;
6. accepts bounded Superset validation evidence where configured;
7. reconciles against fresh DataHub and native state;
8. writes the campaign result to DataHub and verifies the read-back; and
9. runs one privileged final command that either removes the PostgreSQL column
   or refuses with an exact reason.

The focused Workbench renders that same canonical campaign. It can inspect the
decision, consumers, change, evidence, and activity, and it can explicitly pair
with a loopback runtime for inventory and reconciliation. It cannot authorize,
apply, or perform the database action.

## Why DataHub matters

DataHub is not decorative in this project.

In the accepted live-local evidence, repository analysis found one consumer.
DataHub returned 31 downstream consumers over seven complete pages. It exposed
consumers that the repository could not see, and those consumers changed the
decision.

DataHub also supplies the fresh reconciliation surface. When a late Spark
field-level edge appears, Retirement Conductor reverses `READY_TO_RETIRE` to
`UNSAFE` and preserves the producer column. Finally, the product publishes one
durable campaign summary back to DataHub and verifies that a later agent can
read it.

## How we built it

The core is a Python application with an append-only SQLite campaign store and
versioned deterministic policy. DataHub provides graph context and
reconciliation. Git and dbt provide the supported production-shaped consumer
mutation and native validation boundary. A bounded Superset path and a
separately privileged PostgreSQL action provide live-local native proof. Spark
acts as an independent downstream workload in the consequence experiment.

Codex operates the campaign through a project skill and a 16-tool MCP server.
The model can inspect, plan, apply approved changes, validate, reconcile,
publish, and explain. It cannot authorize itself or override the deterministic
decision. PostgreSQL mutation credentials are never exposed to the agent or
browser.

The Workbench is a Next.js interface over the exact same verified manifest and
event stream. Its hosted page shows clearly labeled recorded evidence until an
operator explicitly pairs it with the loopback runtime using a process-scoped
token.

## The experiment that changed our design

Our original design made a short-lived “Retirement Lease” the centerpiece. We
did not assume it was valuable; we tested it against both reusable static
sign-off and a competent fresh CI workflow under the same late-consumer event.

- Static sign-off removed the field, and the Spark consumer failed with
  SQLSTATE `42703`.
- Retirement Conductor saw the late consumer and performed no action.
- Competent fresh CI carried the same checks and also performed no action.

The frozen result was `NO_MATERIAL_ADVANTAGE`, with a recommendation to
`SIMPLIFY`.

We accepted the result. The default product now does the fresh checks and final
action in one trusted invocation. The short-lived plan and intent ledger stay
inside the implementation because they prevent replay and support honest
lost-response recovery, but we no longer claim that carrying a lease makes the
bounded workflow safer than well-built fresh CI.

## Challenges

- **Graph completeness:** an empty search result can never mean “safe.” Every
  DataHub claim carries scope, pagination, freshness, permissions, and known
  limitations.
- **Identity:** a DataHub entity must map one-to-one to the native object before
  the product can change it.
- **Native correctness:** a successful API response is not validation. dbt and
  Superset must execute their own checks.
- **Time and drift:** approval, source fingerprints, graph state, and producer
  schema can change between planning and action.
- **Ambiguous outcomes:** a lost PostgreSQL response cannot be retried blindly.
  The product records outcome unknown and resolves it by native schema reread.
- **Agent authority:** Codex is useful for orchestration and explanation, but
  deterministic code and external human approval retain consequential power.

## Accomplishments

- A real end-to-end Codex campaign produced one exact dbt migration, paused for
  human approval, passed native validation and public PR CI, published to
  DataHub, then reversed when a late consumer appeared.
- The definitive native run committed one exact PostgreSQL `DROP COLUMN`,
  refused replay, and kept the replacement Spark workload healthy.
- The late-consumer arm committed zero producer actions; the static control
  reproduced a real downstream failure.
- A frozen 24-case gauntlet matched all 24 expected decisions, detected 121 of
  121 planted faults, and produced zero false readiness.
- Superset 6.0.0 was mutated, natively executed, reingested to DataHub, reread
  at final-check time, compensated, and tested across 21 refusal cases.
- The public Workbench can pair with the real local campaign engine without
  moving authorization or producer credentials into the browser.

## Open-source contributions

While building the project, we found two issues in DataHub's MCP server:

- [Issue #194](https://github.com/acryldata/mcp-server-datahub/issues/194)
  documents lineage pagination that could silently hide later consumers.
- [PR #195](https://github.com/acryldata/mcp-server-datahub/pull/195) fixes that
  pagination at the GraphQL boundary.
- [PR #196](https://github.com/acryldata/mcp-server-datahub/pull/196) fixes
  misleading deployment-gate diagnostics.

Both pull requests are open and awaiting upstream review. The submission does
not represent them as merged.

## What we learned

Freshness matters more than ceremony. A reusable green approval is dangerous,
but a persistent lease is not automatically better than a correct fresh check.

DataHub is most valuable when its context changes an action, not when it merely
decorates an explanation. The graph must be joined to native validation and an
enforceable producer boundary.

Models are strongest at navigating context, choosing bounded tools, and
explaining evidence. They should not own authorization, state transitions, or
the irreversible decision.

## What's next

The next proof is independent use, not another integration. The current
evidence is author-operated and live-local. We want a data platform engineer
who did not build the project to run the same campaign, expose usability
friction, and tell us whether this retirement pattern occurs often enough to
adopt.

Production work would then focus on deployment-specific graph completeness,
identity, authentication, native validators, and the remaining race between
DataHub observation and the warehouse transaction.

## Built with

DataHub Core and MCP · Codex skills and MCP · Python · SQLite · Git · dbt ·
Superset · PostgreSQL · Spark · Next.js · TypeScript · Docker Compose

## Links

- [Source repository](https://github.com/Arshgill01/RetirementConductor)
- [Live Retirement Workbench](https://retirement-conductor.arshgill01.chatgpt.site/workbench)
- [Definitive public evidence](../../artifacts/public/definitive-consequential-run/README.md)
- [Three-minute agent runbook](../runbooks/AGENT_DEMO.md)
