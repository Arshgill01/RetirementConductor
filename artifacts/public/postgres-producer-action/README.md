# CP-01 PostgreSQL producer action evidence

This bundle records live-local evidence over a deterministic disposable
PostgreSQL fixture. The canonical artifact is [`index.json`](index.json).

The action removed only
`rc_cp01_producer.retirement_lab.orders.legacy_status`, without `CASCADE`,
after exact allowlist, identity, schema, dependency, permission, expiry, and
digest checks. The observer and mutation principals were separate. Native
rereads proved clean commit, lost-response resolution, replay refusal, and one
commit under a concurrent duplicate attempt.

This is not production evidence and not a general PostgreSQL migration
surface. Dropped values are not reversible; experiment recovery is complete
reconstruction of the disposable database. The shared producer gate is frozen
on this branch and is not integrated here.
