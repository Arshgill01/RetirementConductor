import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const siteRoot = new URL("../", import.meta.url);
const publicHtmlUrl = new URL(
  "../public/retirement-conductor.html",
  import.meta.url,
);

async function renderPath(path = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${path}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("root routes visitors to the standalone technical dossier", async () => {
  const response = await renderPath();
  assert.ok([301, 302, 303, 307, 308].includes(response.status));
  assert.equal(
    new URL(response.headers.get("location"), "http://localhost").pathname,
    "/retirement-conductor.html",
  );
});

test("workbench renders a real-runtime connection state without fake campaign data", async () => {
  const response = await renderPath("/workbench");
  const html = await response.text();

  assert.equal(response.status, 200);
  assert.match(html, /Retirement Workbench/);
  assert.match(html, /Reading canonical state/);
  assert.doesNotMatch(html, /A new consumer changed the answer/);
  assert.doesNotMatch(html, /READY_TO_RETIRE|UNSAFE/);
});

test("workbench ships one accepted design and explicit paired-local transport", async () => {
  const [client, page] = await Promise.all([
    readFile(new URL("../app/workbench/workbench-client.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/workbench/page.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(client, /Pair this view to the campaign engine/);
  assert.match(client, /sessionStorage\.setItem\(PAIRING_STORAGE_KEY/);
  assert.match(client, /headers\.set\("Authorization", `Bearer/);
  assert.match(client, /health\.campaign_id !== view\.campaign\.id/);
  assert.doesNotMatch(client, /NEXT_PUBLIC_RETIREMENT_CONDUCTOR_API_URL/);
  assert.doesNotMatch(client, /PrototypeWorkbench|variant/);
  assert.doesNotMatch(page, /workbench-prototypes/);
});

test("pitch route renders the three recording slides", async () => {
  const response = await renderPath("/pitch");
  const html = await response.text();

  assert.equal(response.status, 200);
  assert.match(html, /The new field is live/);
  assert.match(html, /Can we delete the old one/);
  assert.match(html, /DataHub found/);
  assert.match(html, /Retirement Conductor owns the path to deletion/);
  assert.match(html, /The latest evidence decides/);
  assert.match(html, /Remove/);
  assert.match(html, /or refuse/);
});

test("artifact index exposes consequential proof and honest limits", async () => {
  const response = await renderPath("/artifacts");
  const html = await response.text();

  assert.equal(response.status, 200);
  assert.match(html, /Start with the run\. Then inspect every claim\./);
  assert.match(html, /Clean retirement/);
  assert.match(html, /Late-consumer refusal/);
  assert.match(html, /Static sign-off control/);
  assert.match(html, /31 \/ 31/);
  assert.match(html, /NO MATERIAL ADVANTAGE/);
  assert.match(html, /mcp-server-datahub\/pull\/195/);
  assert.match(html, /examples\/agent-run\/migration\.patch/);
  assert.match(html, /no production coverage or independent adoption is claimed/i);
});

test("standalone HTML contains the current product, evidence, and limits", async () => {
  const html = await readFile(publicHtmlUrl, "utf8");

  assert.match(html, /^<!doctype html>/i);
  assert.match(
    html,
    /<title>Retirement Conductor — Verified field retirement<\/title>/,
  );
  assert.match(html, /14\/14/);
  assert.match(html, /zero false readiness/i);
  assert.match(html, /Git\/dbt is the sole automated native mutation boundary/);
  assert.match(html, /RC-018 remains <code>NOT_RUN<\/code>/);
  assert.match(html, /make phase06-benchmark/);
  assert.match(html, /make test-reference-campaign/);
  assert.match(html, /f8f533d5f862e8298e6bd7810e78ada7cc5dbce7/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape/);
});

test("every copy control targets one unique command block", async () => {
  const html = await readFile(publicHtmlUrl, "utf8");
  const copyTargets = [
    ...html.matchAll(/data-copy="([^"]+)"/g),
  ].map((match) => match[1]);
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(
    (match) => match[1],
  );

  assert.ok(copyTargets.length >= 7);
  assert.equal(new Set(copyTargets).size, copyTargets.length);
  for (const target of copyTargets) {
    assert.equal(ids.filter((id) => id === target).length, 1, target);
  }
});

test("starter-only files and metadata are absent", async () => {
  const [page, layout, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  assert.match(page, /redirect\("\/retirement-conductor\.html"\)/);
  assert.match(layout, /Retirement Conductor — Verified field retirement/);
  assert.doesNotMatch(layout, /Starter Project|codex-preview|_sites-preview/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
  assert.doesNotMatch(packageJson, /drizzle/);
  assert.ok(siteRoot);
});
