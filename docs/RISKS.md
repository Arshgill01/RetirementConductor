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
| R-01 | Catalog evidence is incomplete or stale, so readiness overstates coverage | critical | testing | Live Core paging returned 31/31 over seven pages; required-source partial and stale cases fail closed with explicit freshness and limitations | Phase 04 must repeat equivalent fresh inventory and reopen on drift; authenticated inaccessible-source evidence remains |
| R-02 | A DataHub entity cannot be mapped reliably to the exact native object | critical | testing | Phase 03 required one fresh DataHub consumer URN to equal one explicit dbt manifest metadata URN before mapping the exact unique ID and file; zero or multiple matches refuse | Phase 06 must prove the Looker mapping, and recreated/recycled identities remain under R-29 |
| R-03 | Native validation proves syntax but not business equivalence | critical | contained | The supported dbt project runs an explicit semantic-equivalence data test; the compatible change passed while an `order_amount` substitution failed native build | Each later adapter and customer project still needs a meaningful source-native semantic validator |
| R-04 | New consumers appear after inventory and before producer change | critical | open | Fresh reconciliation and short-lived gate decision | Controlled late consumer reopens a previously ready campaign |
| R-05 | A source changes between plan and apply | critical | contained | Live Git/dbt apply rereads branch, commit, clean status, target fingerprint, and attributes; dirty content and a moved commit both refused without overwriting source | Looker needs its own equivalent precondition evidence in phase 06 |
| R-06 | Partial native mutation leaves a consumer in a worse state | critical | testing | One-file Git apply is atomic, actual target equality is checked, rollback restored and validated source, and compensation conflict preserved an intervening owner edit | Phase 07 must still inject interruption at each native write boundary and recover outcome-unknown state |
| R-07 | Overlapping campaigns mutate the same consumer inconsistently | high | contained | The live Git/dbt workflow acquired the same unique native-identity claim only after exact approval and before mutation; the two-campaign integration case refuses a second owner | Looker must use the same campaign claim contract |
| R-08 | Adapter work grows linearly into bespoke consulting | critical | open | Minimal common lifecycle; reuse native tools; no speculative framework | Second live adapter demonstrates shared contract with bounded source-specific code |
| R-09 | The product becomes a report or approval tracker rather than an executor | critical | testing | Phase 03 executed two real Git changes, native dbt validation, rollback, reapply, and receipt acceptance through the campaign | Phase 04 must complete reconciliation and both enforceable producer-gate outcomes |
| R-10 | DataHub becomes decorative because repository tools find the same scope | critical | contained for first product graph | Product live comparison found one configured repository reference and 31 graph consumers, proving a conservative minimum expansion of 30 and adding 31 opaque policy blockers | Repeat the comparison after phase 03 native identity and in the phase 04 reference campaigns |
| R-11 | DataHub Core and Cloud capability differences break portability | high | testing | Live Core capability fingerprint selects GraphQL fallbacks for pagination and document read-back and records unavailable or conditional MCP surfaces | Exercise an authenticated or Cloud boundary without assuming the Core tool union |
| R-12 | DataHub summary storage is mistaken for transactional campaign state | high | contained | Four writes and read-backs updated one DataHub URN while the 12-event SQLite stream remained authoritative; publication receipts never drive policy | Phase 04 write failure and final publication must remain resumable from local state |
| R-13 | Digests are presented as proof of authorship | high | contained | Phase 00 verifies content integrity and labels fixture principal/mode separately; the contract makes no authorship claim | Native phases record and verify trusted run/principal provenance independently of digests |
| R-14 | Apply credentials are too broad or leak through evidence | critical | testing | Apply is opt-in, target-bound approval is required before the native claim, plan-only mode left Git unchanged, validation receives an allowlisted environment, and public/secret scans pass | Looker least privilege and deployed secret-reference handling remain |
| R-15 | Query history or raw evidence exposes sensitive SQL or data | high | testing | Query-bearing keys and email/secret fields are redacted before content-addressed ignored storage; public and secret scans pass | Phase 07 must document retention/deletion and exercise non-empty sensitive query evidence |
| R-16 | Waivers either deadlock campaigns or become a quiet bypass | high | contained | Distinct digest-bound waiver records require authority, scope, reason, residual risk, and expiry; default policy blocks and allowed waiver remains visible | Live operator and gate views must retain the waiver distinction |
| R-17 | A disappearing lineage edge is treated as proof of migration | critical | contained by contract | Closure requires native receipt, verified removal, or proved non-applicability | Edge disappearance without a receipt leaves the consumer unresolved |
| R-18 | Native retries duplicate or broaden mutations | high | testing | Repeated Git/dbt apply returned the same digest and retained one native commit; exact actual targets are checked before receipt acceptance | Lost-response recovery remains under R-31, and Looker retry semantics remain |
| R-19 | Validation queries create excessive cost or side effects | high | testing | DuckDB validation uses a disposable copy, one thread, command timeout, file/process/memory bounds, and no production warehouse credentials | A live nonlocal validator still needs native cost and cancellation limits |
| R-20 | Final producer action bypasses the gate | critical | open | Separate CI command and separately privileged producer workflow | A representative producer migration cannot proceed on non-ready state |
| R-21 | Customers perform retirements too rarely to support ongoing adoption | high | open | Target teams with recurring schema evolution; measure coordination burden | Interviews and observed workflows show recurring use and a budget owner |
| R-22 | A close competitor closes the documented cross-system execution gap | high | open | Maintain qualified capability matrix; win on open protocol and DataHub fit | Current primary-source review before major positioning changes |
| R-23 | The system cannot resume deterministically after interruption | high | contained | Append-only events, prefix-safe cache repair, and injected pre-insert, post-insert, and post-commit crashes reproduce one manifest without duplicates | Native outcome-unknown recovery remains adapter-specific phase 03/06 evidence |
| R-24 | Generated changes are overbroad, templated, or miss indirect references | high | contained | Discovery records bounded text, dbt manifest, and compiled SQL separately; alias, macro/generated, and `SELECT *` uncertainty remains visible, while apply changes only one explicit manifest-mapped file | Broader generated-code patterns remain outside the supported repository shape |
| R-25 | Source deletion or branch movement invalidates the evidence chain | high | testing | Source commit, branch, and file fingerprints are pinned; a clean moved commit refused before mutation | Missing repository, deleted target, force-move after receipt, and gate-time invalidation still need phase 04/07 evidence |
| R-26 | The campaign state machine can remain blocked forever | medium | open | Explicit owner actions, removal, non-applicability, and policy-bound waiver | Real unresolved cases have clear accountable paths without being mislabeled |
| R-27 | Clock skew or an untrusted wall clock makes freshness and expiration decisions incorrect | critical | testing | Injected clock fixtures refuse rollback, invalid/naive time, future evidence, boundary expiry, and excessive skew | Deployment must establish a trusted clock and live source freshness |
| R-28 | A repository, dbt project, dependency, macro, or hook executes untrusted code outside the validation scope | critical | contained | Bubblewrap runs a copied tree with unshared network, no host home or source mount, an allowlisted environment, and resource limits; symlink, dependency, path, secret-read, subprocess, network, and Git-hook probes were refused or contained | Evidence is specific to the observed Linux/bubblewrap boundary and public fixture; other kernels require equivalent isolation proof |
| R-29 | A deleted and recreated native object is mistaken for the previously approved identity | critical | open | Bind immutable native ID, creation/version evidence, content fingerprint, and graph mapping | Recreated same-name and recycled-ID cases invalidate plans and receipts |
| R-30 | The replacement field or its compatibility changes after validation but before the producer gate | critical | testing | Phase 03 pinned matching live DataHub and dbt `VARCHAR` evidence into the plan and receipt | Phase 04 must reread replacement identity/type and refuse removal or compatibility drift at gate time |
| R-31 | A timeout or cancellation after apply leaves mutation outcome unknown and a retry duplicates or widens the change | critical | open | Durable intent, native idempotency key where supported, reread before retry | Lost-response and interrupted-apply tests reconcile actual state before retry |
| R-32 | Table-level lineage is presented as proof of a field-level dependency or closure | critical | contained for DataHub adapter | Live table-only edges retain an explicit limitation and all 31 consumers remain opaque; only observed column edges receive column confidence | Phase 03/04 native receipts and reconciliation must preserve the same distinction |
| R-33 | Policy, configuration, validator, or authorization changes between validation and gate | critical | testing | Kernel binds and rechecks policy, validator configuration, and authorization digests; changed inputs refuse without an event | Phase 04 gate must reread and enforce the same bindings live |
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
