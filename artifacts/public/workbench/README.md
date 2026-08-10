# Retirement Workbench acceptance

Behavior commit: `17ec47f77599e0471ee1f3edf7bb0be01ad44168`.

The public site previews were captured from `/workbench` while the loopback API read
the retained 18-event live-local agent campaign with actions disabled. They are
rendered operator evidence, not campaign authority and not proof of production
coverage.

- `site/public/workbench-desktop.png`: 1600 × 1000; SHA-256
  `350e83093bbea1c3fff8ff3f52924a1842b48cbd6cfcb5fb09f0e7ecf2ceb64c`;
- `site/public/workbench-mobile.png`: 390 × 844; SHA-256
  `65a991c557629d48075e46240f46cbe8ed9ac41561d018d8b90c349e687a2283`.

The public recorded projection at `site/public/workbench-recorded.json` has
SHA-256
`c702bd127679965537cb821474c53900afaf2ba71aa43b882e59d718acdd0af9`
and embeds canonical manifest digest
`sha256:49aa07fa4afd1e065c0eedfbaaa7074be0827a9917e9941047183ba49a7efe28`.
It is explicitly labeled `recorded-evidence` and cannot dispatch an operation.

The finalized hosted-to-loopback acceptance is recorded in
`pairing-acceptance.json`; SHA-256
`f368ddd4342ea236dcb861a91396592021b77e14acec8740137ca6a2a826cdf6`.
Normal Chrome required an explicit Local Network Access grant, then the public
version 4 page replaced its recording with the matching canonical campaign and
displayed `PAIRED READ ONLY`. No runtime action or privileged boundary was
enabled for that acceptance.
