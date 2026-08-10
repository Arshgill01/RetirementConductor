# Static sign-off versus Retirement Lease

This frozen comparison isolates the value of revocable permission after impact
analysis has already returned green.

Both arms begin from the same inspected live-local `READY_TO_RETIRE` manifest
and receive the same late exact-field DataHub consumer intervention. The
executable static arm persists the original sign-off and has no observation or
revocation operation, so it remains stale green. Retirement Conductor observes
the change, becomes `UNSAFE`, invalidates the issued lease, and refuses the
preserved producer plan with zero actions.

Start with [`index.json`](index.json) and [`report.json`](report.json). The
static arm is a deliberately minimal workflow contract, not a claim about a
named catalog or ticketing product. The intervention and lease outcome are
bound to the existing WS-03 live-local evidence rather than a new production
run.
