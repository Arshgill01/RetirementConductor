# Retirement Conductor technical dossier

This directory contains the public, standalone technical pitch for Retirement
Conductor.

The primary artifact is
[`public/retirement-conductor.html`](public/retirement-conductor.html). It is a
self-contained HTML document with inline CSS and progressive-enhancement
JavaScript. The root application route redirects to that file so the deployed
site and the directly shareable HTML stay identical.

## Local development

```bash
npm ci
npm run dev
```

Open `http://localhost:3000/`. The root redirects to
`/retirement-conductor.html`.

## Validation

```bash
npm test
npm run lint
```

`npm test` builds the Cloudflare Worker-compatible Sites output and verifies
the root redirect, public HTML structure, copy controls, current evidence
claims, and removal of starter metadata.
