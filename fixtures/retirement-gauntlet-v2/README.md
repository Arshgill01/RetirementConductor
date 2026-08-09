# Retirement Gauntlet v2 frozen truth set

This directory is the independent, pre-observation truth boundary for TE-02.
`corpus.json` declares causal inputs and exact controlled consumer identities.
`oracle.json` declares the expected campaign decision and stable blocker or
review codes. Neither file is generated from campaign state or imports product
policy.

`frozen-digests.json` binds the exact bytes that were committed before any
product case was executed. The runner only verifies these files; it never
rewrites them. Raw run state belongs under the ignored
`.retirement-conductor/gauntlet-v2/` directory.

Evidence classification: deterministic fixture truth. A later live-local run
over these fixtures proves integration behavior, not production coverage.
