import type { Metadata } from "next";
import "./artifacts.css";

export const metadata: Metadata = {
  title: "Public Artifacts — Retirement Conductor",
  description:
    "A judge-facing index of Retirement Conductor's consequential run, exact changes, DataHub evidence, and adversarial results.",
};

const repo = "https://github.com/Arshgill01/RetirementConductor/blob/main";
const tree = "https://github.com/Arshgill01/RetirementConductor/tree/main";

type Artifact = {
  title: string;
  description: string;
  format: string;
  result: string;
  tone?: "safe" | "blocked" | "plain";
  href: string;
};

const decisiveRun: Artifact[] = [
  {
    title: "Clean retirement",
    description:
      "One PostgreSQL DROP COLUMN committed exactly once. The replacement Spark workload kept the same 128-row output digest, and replay was refused.",
    format: "JSON · native run",
    result: "COMMITTED ONCE",
    tone: "safe",
    href: `${repo}/artifacts/public/definitive-consequential-run/retirement-conductor-clean.json`,
  },
  {
    title: "Late-consumer refusal",
    description:
      "Fresh DataHub evidence discovered a late Spark consumer. The lease became INVALIDATED, zero destructive statements committed, and the legacy column remained present.",
    format: "JSON · native run",
    result: "REFUSED BEFORE ACTION",
    tone: "blocked",
    href: `${repo}/artifacts/public/definitive-consequential-run/retirement-conductor-late.json`,
  },
  {
    title: "Static sign-off control",
    description:
      "The point-in-time approval stayed green, the column was dropped, and the legacy Spark workload failed with SQLSTATE 42703.",
    format: "JSON · control",
    result: "NATIVE BREAKAGE",
    tone: "blocked",
    href: `${repo}/artifacts/public/definitive-consequential-run/point-in-time-static.json`,
  },
];

const exactChange: Artifact[] = [
  {
    title: "Exact dbt migration",
    description:
      "The reviewable one-file patch that moves the authorized consumer from legacy_status to order_status.",
    format: "PATCH · transformation",
    result: "1 FILE",
    href: `${repo}/examples/agent-run/migration.patch`,
  },
  {
    title: "Native change receipt",
    description:
      "The accepted target, source version, plan binding, and dbt parse, seed, build, and test result.",
    format: "JSON · receipt",
    result: "PASSED",
    tone: "safe",
    href: `${repo}/examples/agent-run/change-receipt.json`,
  },
  {
    title: "Agent transcript",
    description:
      "A public-safe stage-by-stage record of the Codex run, including the external authorization pause and the later reversal.",
    format: "MARKDOWN · transcript",
    result: "5 STAGES",
    href: `${repo}/examples/agent-run/agent-transcript.md`,
  },
  {
    title: "Public PR and passing CI",
    description:
      "The exact generated dbt change as a reviewable GitHub pull request with the semantic-dbt check attached to its head commit.",
    format: "GITHUB · pull request",
    result: "CI PASSED",
    tone: "safe",
    href: "https://github.com/Arshgill01/retirement-conductor-definitive-acceptance/pull/1",
  },
];

const datahubEvidence: Artifact[] = [
  {
    title: "DataHub inventory expansion",
    description:
      "Repository inspection found one consumer. Fully paged DataHub lineage returned 31 across seven pages—a minimum expansion of 30 consumers.",
    format: "JSON · live evidence",
    result: "31 / 31",
    tone: "safe",
    href: `${repo}/artifacts/public/phase02/inventory-evidence.json`,
  },
  {
    title: "Unified agent campaign",
    description:
      "The digest-bound run joining Codex, DataHub discovery, one exact PR, native validation, publication read-back, lease issuance, and late-consumer invalidation.",
    format: "JSON · evidence index",
    result: "VERIFIED",
    tone: "safe",
    href: `${repo}/artifacts/public/definitive-unified-run/index.json`,
  },
  {
    title: "Lineage pagination fix",
    description:
      "Our upstream DataHub MCP contribution fixes a GraphQL pagination boundary that could silently hide later consumers.",
    format: "GITHUB · upstream PR",
    result: "PR #195",
    href: "https://github.com/acryldata/mcp-server-datahub/pull/195",
  },
  {
    title: "Deployment-gate diagnostics fix",
    description:
      "A second upstream contribution corrects diagnostics that could misstate the DataHub MCP deployment gate.",
    format: "GITHUB · upstream PR",
    result: "PR #196",
    href: "https://github.com/acryldata/mcp-server-datahub/pull/196",
  },
];

const stressAndTruth: Artifact[] = [
  {
    title: "Retirement Gauntlet v2",
    description:
      "Twenty-four frozen cases: 4 READY, 6 BLOCKED, 10 UNSAFE, and 4 REVIEW. All matched, with zero false readiness and zero unexpected closure.",
    format: "JSON · benchmark",
    result: "24 / 24",
    tone: "safe",
    href: `${repo}/artifacts/public/retirement-gauntlet-v2/index.json`,
  },
  {
    title: "Native breakage outcome lab",
    description:
      "Two clean Spark/JDBC sequences prove the consequence of deleting too early: legacy_status disappears and the workload exits 42 with SQLSTATE 42703.",
    format: "JSON · native lab",
    result: "BREAKAGE PROVED",
    tone: "blocked",
    href: `${repo}/artifacts/public/native-breakage-outcome-lab/index.json`,
  },
  {
    title: "Nested-model ablation",
    description:
      "Across 135 attempts, DataHub context improved fault coverage but nested Gemini failed the value threshold. We removed the extra model layer.",
    format: "MARKDOWN · experiment",
    result: "REMOVE GEMINI",
    href: `${repo}/artifacts/public/semantic-ablation-v2/REPORT.md`,
  },
  {
    title: "Agent boundary ablation",
    description:
      "The project skill and MCP improved completion and reduced calls and retries. Shell exposure remained, so capability containment is explicitly unclaimed.",
    format: "JSON · experiment",
    result: "KEEP · BOUNDEDNESS UNKNOWN",
    href: `${repo}/artifacts/public/agent-ablation/report.json`,
  },
  {
    title: "Fresh-CI comparison",
    description:
      "The honest counterfactual: competent fresh CI matched the frozen safety properties. Retirement Conductor's narrower value is the joined workflow and durable authority protocol.",
    format: "JSON · comparison",
    result: "NO MATERIAL ADVANTAGE",
    href: `${repo}/artifacts/public/definitive-consequential-run/comparison.json`,
  },
];

const evidencePath = [
  ["01", "Consequential run", "decisive-run"],
  ["02", "Exact change", "exact-change"],
  ["03", "DataHub", "datahub-evidence"],
  ["04", "Stress & truth", "stress-truth"],
] as const;

function ArtifactRows({ artifacts }: { artifacts: Artifact[] }) {
  return (
    <div className="rca-rows">
      {artifacts.map((artifact) => (
        <a
          className="rca-row"
          href={artifact.href}
          key={artifact.title}
          target="_blank"
          rel="noreferrer"
        >
          <div className="rca-row-title">
            <span>{artifact.format}</span>
            <h3>{artifact.title}</h3>
          </div>
          <p>{artifact.description}</p>
          <strong data-tone={artifact.tone ?? "plain"}>{artifact.result}</strong>
          <i aria-hidden="true">↗</i>
        </a>
      ))}
    </div>
  );
}

export default function ArtifactsPage() {
  return (
    <main className="rca-shell">
      <a className="rca-skip" href="#artifact-content">
        Skip to artifacts
      </a>

      <header className="rca-topbar">
        <a className="rca-wordmark" href="/workbench">
          Retirement Workbench
        </a>
        <p>
          <span>Evidence</span>
          <strong>Public artifacts</strong>
          <b aria-hidden="true">/</b>
          <strong>judge path</strong>
        </p>
        <a
          className="rca-repo-link"
          href="https://github.com/Arshgill01/RetirementConductor"
          target="_blank"
          rel="noreferrer"
        >
          GitHub repository ↗
        </a>
      </header>

      <aside className="rca-rail" aria-label="Artifact sections">
        <ol>
          {evidencePath.map(([number, label, id], index) => (
            <li key={id} data-current={index === 0 ? "true" : undefined}>
              <a href={`#${id}`}>
                <span>{number}</span>
                <strong>{label}</strong>
                <i aria-hidden="true" />
              </a>
            </li>
          ))}
        </ol>
      </aside>

      <div className="rca-canvas" id="artifact-content">
        <header className="rca-hero">
          <p>Inspect without running the project</p>
          <h1>Start with the run. Then inspect every claim.</h1>
          <div className="rca-intro">
            <p>
              These are the exact public-safe outputs behind Retirement Conductor:
              native actions, reviewable changes, DataHub evidence, refusals, and
              the experiments that changed what we shipped.
            </p>
            <dl>
              <div>
                <dt>Clean path</dt>
                <dd>Real PostgreSQL drop</dd>
              </div>
              <div>
                <dt>Changed world</dt>
                <dd>Zero destructive actions</dd>
              </div>
              <div>
                <dt>Evidence policy</dt>
                <dd>No hidden caveats</dd>
              </div>
            </dl>
          </div>
        </header>

        <section className="rca-section" id="decisive-run">
          <header>
            <span>01</span>
            <div>
              <p>The shortest judge path</p>
              <h2>The consequential run</h2>
            </div>
          </header>
          <ArtifactRows artifacts={decisiveRun} />
          <a className="rca-folder-link" href={`${tree}/artifacts/public/definitive-consequential-run`} target="_blank" rel="noreferrer">
            Open the complete digest-bound evidence package ↗
          </a>
        </section>

        <section className="rca-section" id="exact-change">
          <header>
            <span>02</span>
            <div>
              <p>What the agent actually changed</p>
              <h2>Exact change and validation</h2>
            </div>
          </header>
          <ArtifactRows artifacts={exactChange} />
          <a className="rca-folder-link" href={`${tree}/examples/agent-run`} target="_blank" rel="noreferrer">
            Open the complete agent-run example ↗
          </a>
        </section>

        <section className="rca-section" id="datahub-evidence">
          <header>
            <span>03</span>
            <div>
              <p>Where context changed the answer</p>
              <h2>DataHub evidence and contributions</h2>
            </div>
          </header>
          <ArtifactRows artifacts={datahubEvidence} />
        </section>

        <section className="rca-section" id="stress-truth">
          <header>
            <span>04</span>
            <div>
              <p>Successes, failures, and negative results</p>
              <h2>Stress tests and product truth</h2>
            </div>
          </header>
          <ArtifactRows artifacts={stressAndTruth} />
        </section>

        <footer className="rca-footer">
          <p>
            Every linked repository artifact is public-safe and inspectable. The
            native runs used disposable local systems; no production coverage or
            independent adoption is claimed.
          </p>
          <nav aria-label="Related Retirement Conductor pages">
            <a href="/workbench">Workbench</a>
            <a href="/pitch">Three-minute story</a>
            <a href="/retirement-conductor.html">Technical dossier</a>
          </nav>
        </footer>
      </div>
    </main>
  );
}
