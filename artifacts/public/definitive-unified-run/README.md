# TE-04 definitive unified run

`index.json` is the public-safe, digest-bound index for the definitive Codex
campaign. It binds one exact Git/dbt migration to a public pull request and
passing CI check, a verified DataHub publication, a short-lived Retirement
Lease, and a later cache-bypassed consumer observation that invalidated the
lease and refused the producer gate without writing a sentinel.

The result is bounded by the recorded disposable evidence envelope. It is not
a claim of universal safety or capability isolation. Raw Codex traces remain
local because they contain machine-specific paths; their digests and
classification are recorded in the public index.

Offline verification:

```bash
uv run python scripts/generate_definitive_unified_evidence.py verify
```
