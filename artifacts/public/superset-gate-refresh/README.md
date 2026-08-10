# Superset gate-time native refresh

This live-local CP-02 evidence tests whether a read-only verifier can reconstruct
the critical native Superset facts immediately before a producer action. It
binds the accepted campaign artifacts to the exact dataset, saved chart,
database, SQL mapping, forced execution result, adapter version, server version,
configuration, and DataHub identity.

Start with [`index.json`](index.json) and [`evidence.json`](evidence.json). The
matrix includes the unchanged control and every required identity, source,
semantic, integrity, permission, outage, timeout, response-shape, version, and
freshness refusal. Public evidence contains only safe identities and digests;
raw responses, runtime credentials, query results, and machine paths remain
private and ignored.

This is bounded live-local evidence against a disposable Superset service. The
native verifier complements, but does not replace, the final gate's fresh
DataHub inventory: DataHub proves graph membership while Superset SQL and forced
execution prove the exact native field fact.
