# Risk register

This register tracks threats to product substance, correctness, safety, and
adoption. A risk closes only when observed evidence addresses it.

Status values:

- `open`: material and not yet tested;
- `testing`: an active phase has an explicit experiment;
- `contained`: mitigated for the supported scope;
- `reframed`: evidence changed the product boundary;
- `accepted`: residual risk is explicit and owned.

## Active risks

| ID | Risk | Severity | Status | Current control | Evidence required |
|---|---|---:|---|---|---|
| R-01 | Catalog evidence is incomplete or stale, so readiness overstates coverage | critical | open | Required evidence envelope, pagination and freshness gates | Live incomplete, truncated, stale, and inaccessible-source cases all refuse |
| R-02 | A DataHub entity cannot be mapped reliably to the exact native object | critical | open | One-to-one identity contract; names cannot authorize apply | Live mappings for Git/dbt and Looker, plus zero-match and multi-match refusals |
| R-03 | Native validation proves syntax but not business equivalence | critical | open | Validator-specific semantic checks and explicit review state | A compatible change passes and a plausible semantically wrong change does not become ready |
| R-04 | New consumers appear after inventory and before producer change | critical | open | Fresh reconciliation and short-lived gate decision | Controlled late consumer reopens a previously ready campaign |
| R-05 | A source changes between plan and apply | critical | contained for prior dbt experiment | Content/source fingerprints immediately before apply | Product implementation reproduces stale-source refusal without mutation |
| R-06 | Partial native mutation leaves a consumer in a worse state | critical | open | Capture recovery state; explicit compensation and verification | Fault injection after partial apply proves either restoration or durable unsafe state |
| R-07 | Overlapping campaigns mutate the same consumer inconsistently | high | open | Detect native-identity overlap and refuse concurrent apply | Two campaigns targeting one consumer cannot both enter apply |
| R-08 | Adapter work grows linearly into bespoke consulting | critical | open | Minimal common lifecycle; reuse native tools; no speculative framework | Second live adapter demonstrates shared contract with bounded source-specific code |
| R-09 | The product becomes a report or approval tracker rather than an executor | critical | testing | Complete Git/dbt vertical and producer-side gate are mandatory | Real source change, native validation, reconciliation, and enforceable refusal all execute |
| R-10 | DataHub becomes decorative because repository tools find the same scope | critical | contained for prior experiment | Compare declared repository scope with live graph scope | Product rerun shows DataHub adds consequential consumers and changes policy outcome |
| R-11 | DataHub Core and Cloud capability differences break portability | high | open | Live capability inspection; avoid assuming the documented union | Same boundary handles missing tools explicitly on Core and records Cloud-only options |
| R-12 | DataHub summary storage is mistaken for transactional campaign state | high | contained by design | SQLite event state; DataHub used for shared summary and reconciliation | Restart and resume work despite delayed DataHub indexing or write failure |
| R-13 | Digests are presented as proof of authorship | high | contained by contract | Call digests integrity checks; record native run/principal provenance | Receipt verification distinguishes content integrity from trusted producer identity |
| R-14 | Apply credentials are too broad or leak through evidence | critical | open | Separate capabilities, secret references, redaction, least privilege | Secret scanning plus negative tests prove plan-only principals cannot apply |
| R-15 | Query history or raw evidence exposes sensitive SQL or data | high | open | Store minimum safe claims; raw private artifacts ignored and access-controlled | Redaction tests and a documented data-retention policy |
| R-16 | Waivers either deadlock campaigns or become a quiet bypass | high | open | Distinct `WAIVED` state, named authority, scope, reason, expiration, policy | Expired, unsigned, wrong-scope, and policy-forbidden waivers refuse readiness |
| R-17 | A disappearing lineage edge is treated as proof of migration | critical | contained by contract | Closure requires native receipt, verified removal, or proved non-applicability | Edge disappearance without a receipt leaves the consumer unresolved |
| R-18 | Native retries duplicate or broaden mutations | high | open | Idempotency keys where supported, source versions, actual-target comparison | Repeated apply yields one change or a stable no-op receipt |
| R-19 | Validation queries create excessive cost or side effects | high | open | Safe fixtures, bounded query scope, explicit execution permission | Cost/scope limits refuse a validator before an unsafe query executes |
| R-20 | Final producer action bypasses the gate | critical | open | Separate CI command and separately privileged producer workflow | A representative producer migration cannot proceed on non-ready state |
| R-21 | Customers perform retirements too rarely to support ongoing adoption | high | open | Target teams with recurring schema evolution; measure coordination burden | Interviews and observed workflows show recurring use and a budget owner |
| R-22 | A close competitor closes the documented cross-system execution gap | high | open | Maintain qualified capability matrix; win on open protocol and DataHub fit | Current primary-source review before major positioning changes |
| R-23 | The system cannot resume deterministically after interruption | high | open | Append-oriented events, idempotent steps, durable attempts | Interrupt at every stage and reproduce the same safe state after restart |
| R-24 | Generated changes are overbroad, templated, or miss indirect references | high | open | dbt manifest, repository evidence layers, target allowlist, native tests | Aliases, macros, generated SQL, and unauthorized-file fixtures behave safely |
| R-25 | Source deletion or branch movement invalidates the evidence chain | high | open | Pin immutable commits and native IDs; capture safe recovery data | Branch force-move and missing source cases invalidate prior receipts |
| R-26 | The campaign state machine can remain blocked forever | medium | open | Explicit owner actions, removal, non-applicability, and policy-bound waiver | Real unresolved cases have clear accountable paths without being mislabeled |
| R-27 | Clock skew or an untrusted wall clock makes freshness and expiration decisions incorrect | critical | open | Injected clock, recorded observation time, conservative skew policy | Past, future, rollback, and boundary-time fixtures never create false readiness |
| R-28 | A repository, dbt project, dependency, macro, or hook executes untrusted code outside the validation scope | critical | open | Isolated process, disposable credentials, bounded files, environment and network controls | Malicious project fixtures cannot read secrets, escape paths, or mutate external resources |
| R-29 | A deleted and recreated native object is mistaken for the previously approved identity | critical | open | Bind immutable native ID, creation/version evidence, content fingerprint, and graph mapping | Recreated same-name and recycled-ID cases invalidate plans and receipts |
| R-30 | The replacement field or its compatibility changes after validation but before the producer gate | critical | open | Pin and reread replacement schema plus semantic preconditions at final gate | Replacement removal, type drift, and compatibility drift all refuse |
| R-31 | A timeout or cancellation after apply leaves mutation outcome unknown and a retry duplicates or widens the change | critical | open | Durable intent, native idempotency key where supported, reread before retry | Lost-response and interrupted-apply tests reconcile actual state before retry |
| R-32 | Table-level lineage is presented as proof of a field-level dependency or closure | critical | open | Preserve evidence granularity and require field-native evidence for field decisions | Table-only edges remain qualified and cannot independently authorize mutation or closure |
| R-33 | Policy, configuration, validator, or authorization changes between validation and gate | critical | open | Version and digest executable inputs; final gate rechecks every bound value | Changed policy, command, scope, or approval invalidates readiness |
| R-34 | The producer gate trusts an unproven artifact or fails open when campaign state is unavailable | critical | open | Verify commit/run provenance, manifest and receipt digests, durable state, and publication read-back | Untrusted CI, missing store, tampered artifact, and unavailable read-back all refuse |
| R-35 | A green gate result is replayed or state changes between the check and the producer action | critical | open | Bind one gate invocation to the exact producer plan and trusted run; never persist reusable success | Replayed result, changed state, wrong producer plan, and delayed action all refuse |
| R-36 | Two runners use divergent local campaign stores and each believes it is authoritative | critical | open | Explicit single-writer deployment identity and lock; refuse unsupported multi-writer mode | Two-runner and copied-database tests cannot produce independent readiness |

## Product-pressure interpretation

### Highest substance risk

R-08 and R-09 decide whether Retirement Conductor is a product. If every
platform requires a different orchestrator, or if the work ends in a report,
the cross-system thesis fails.

### Highest safety risks

R-01, R-02, R-04, R-06, R-14, R-17, R-20, and R-27 through R-36 can produce
a false `READY_TO_RETIRE`. They take priority over breadth and visual polish.

### Highest adoption risk

R-21 is not solved by more code. The complete vertical can prove capability,
but only real users can prove frequency, willingness to adopt, and budget.

## Review rule

Every phase document names the risks it changes. When evidence is added:

1. link the artifact or test;
2. explain what the result proves and does not prove;
3. update status;
4. add a new risk when the result exposes one;
5. never close a broader risk with a narrower fixture.
