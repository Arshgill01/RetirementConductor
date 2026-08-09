"use client";

// Prototype question: which genuinely different product metaphor makes a retirement decision easiest to operate and trust?

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { Consumer, WorkbenchView } from "./workbench-client";

const prototypeVariants = [
  { key: "operator", label: "The Operator" },
  { key: "radar", label: "Evidence Radar" },
  { key: "native-review", label: "Native Review" },
] as const;

export type PrototypeVariant = (typeof prototypeVariants)[number]["key"];

export function isPrototypeVariant(value: string | null): value is PrototypeVariant {
  return prototypeVariants.some((variant) => variant.key === value);
}

function fieldName(value: string) {
  return value.split(".").at(-1) ?? value;
}

function shortId(value: string, visible = 18) {
  return value.length > visible ? `${value.slice(0, visible - 8)}…${value.slice(-6)}` : value;
}

function formatTime(value: string | null) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "UTC",
  }).format(date);
}

function PrototypeSwitcher({ variant }: { variant: PrototypeVariant }) {
  const router = useRouter();
  const pathname = usePathname();
  const currentIndex = prototypeVariants.findIndex((item) => item.key === variant);

  function select(index: number) {
    const next = prototypeVariants[(index + prototypeVariants.length) % prototypeVariants.length];
    router.replace(`${pathname}?variant=${next.key}`, { scroll: false });
  }

  useEffect(() => {
    function handleKeydown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (
        target?.matches("input, textarea, select, [contenteditable='true']") ||
        (event.key !== "ArrowLeft" && event.key !== "ArrowRight")
      ) {
        return;
      }
      event.preventDefault();
      select(currentIndex + (event.key === "ArrowRight" ? 1 : -1));
    }
    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  });

  if (process.env.NODE_ENV === "production") return null;

  return (
    <div className="rcp-switcher" aria-label="Prototype variants">
      <button type="button" onClick={() => select(currentIndex - 1)} aria-label="Previous design">
        ←
      </button>
      <span>
        <b>{prototypeVariants[currentIndex].label}</b>
        <small>{currentIndex + 1} of {prototypeVariants.length}</small>
      </span>
      <button type="button" onClick={() => select(currentIndex + 1)} aria-label="Next design">
        →
      </button>
      <a href={pathname}>Baseline</a>
    </div>
  );
}

type OperatorMoment = {
  verb: string;
  statement: string;
  answer: string;
  source: string;
};

function operatorMoments(data: WorkbenchView): OperatorMoment[] {
  const knownCount = data.consumers.filter((consumer) => !consumer.newly_observed).length;
  return [
    {
      verb: "Inspect",
      statement: `Can I retire ${fieldName(data.target)}?`,
      answer: `${knownCount} known consumer was found inside the declared DataHub and Git scope.`,
      source: data.evidence.coverage.label,
    },
    {
      verb: "Propose",
      statement: "What must change first?",
      answer: `Change only ${data.change.paths[0] ?? "the authorized dbt path"}. No producer action is included.`,
      source: "Deterministic plan bound to the source fingerprint",
    },
    {
      verb: "Validate",
      statement: "Did the authorized migration work?",
      answer: data.change.receipt
        ? `Yes. Native ${data.change.receipt.adapter} validation returned ${data.change.receipt.result}.`
        : "No accepted native validation receipt is recorded.",
      source: data.change.receipt ? `Receipt ${shortId(data.change.receipt.digest, 28)}` : "Receipt missing",
    },
    {
      verb: "Reconcile",
      statement: "Can the producer field be retired now?",
      answer: `No. ${data.summary.cause}`,
      source: `Fresh evidence at ${formatTime(data.evidence.captured_at)} UTC`,
    },
  ];
}

function TheOperator({ data }: { data: WorkbenchView }) {
  const moments = operatorMoments(data);
  const [momentIndex, setMomentIndex] = useState(moments.length - 1);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const moment = moments[momentIndex];
  const newConsumer = data.consumers.find((consumer) => consumer.newly_observed);

  return (
    <main className="rcp-root rcp-operator">
      <nav className="rcp-operator-nav" aria-label="Workbench navigation">
        <a href="/workbench">Retirement Conductor</a>
        <span>{data.mode === "recorded-evidence" ? "Recorded campaign" : "Live campaign"}</span>
      </nav>

      <section className="rcp-operator-dialogue" aria-live="polite">
        <p className="rcp-operator-question">{moment.statement}</p>
        <div className="rcp-operator-answer" key={moment.verb}>
          <span>{moment.verb}</span>
          <h1>{moment.answer}</h1>
          <p>{moment.source}</p>
        </div>
      </section>

      <footer className="rcp-operator-controls">
        <div className="rcp-operator-sequence" aria-label="Investigation sequence">
          {moments.map((item, index) => (
            <button
              type="button"
              key={item.verb}
              aria-current={index === momentIndex ? "step" : undefined}
              onClick={() => {
                setMomentIndex(index);
                setEvidenceOpen(false);
              }}
            >
              <span>{index + 1}</span>
              {item.verb}
            </button>
          ))}
        </div>
        <button
          className="rcp-operator-evidence-button"
          type="button"
          aria-expanded={evidenceOpen}
          onClick={() => setEvidenceOpen((open) => !open)}
        >
          {evidenceOpen ? "Hide evidence" : "Show exact evidence"}
        </button>
      </footer>

      {evidenceOpen && (
        <section className="rcp-operator-evidence" aria-label="Exact evidence">
          <button type="button" onClick={() => setEvidenceOpen(false)} aria-label="Close evidence">Close</button>
          <dl>
            <div><dt>Decision</dt><dd>{data.decision}</dd></div>
            <div><dt>New consumer</dt><dd>{newConsumer?.id ?? "None"}</dd></div>
            <div><dt>Consumer state</dt><dd>{newConsumer?.receipt_state ?? "No receipt"}</dd></div>
            <div><dt>Producer lease</dt><dd>Invalidated</dd></div>
          </dl>
          <p>{data.primary_action.description}</p>
        </section>
      )}
    </main>
  );
}

type RadarSelection = {
  title: string;
  role: string;
  fact: string;
  tone: "datahub" | "git" | "validation" | "known" | "late" | "field";
};

function EvidenceRadar({ data }: { data: WorkbenchView }) {
  const known = data.consumers.find((consumer) => !consumer.newly_observed);
  const late = data.consumers.find((consumer) => consumer.newly_observed);
  const selections: Record<string, RadarSelection> = {
    field: {
      title: fieldName(data.target),
      role: "Field proposed for retirement",
      fact: `Replacement: ${fieldName(data.replacement)}`,
      tone: "field",
    },
    datahub: {
      title: "DataHub",
      role: "Context graph and reconciliation",
      fact: `${data.evidence.sources[0]?.scope.returned_total ?? 0} of ${data.evidence.sources[0]?.scope.reported_total ?? 0} consumers returned across ${data.evidence.sources[0]?.scope.pages ?? 0} pages`,
      tone: "datahub",
    },
    git: {
      title: "Git / dbt",
      role: "Native mutation boundary",
      fact: data.change.paths[0] ?? "No changed path recorded",
      tone: "git",
    },
    validation: {
      title: "Native receipt",
      role: "Validation evidence",
      fact: data.change.receipt ? `${data.change.receipt.adapter}: ${data.change.receipt.result}` : "Missing",
      tone: "validation",
    },
    known: {
      title: shortId(known?.id ?? "Known consumer", 24),
      role: "Inside frozen inventory",
      fact: known?.receipt_state ?? "No native receipt",
      tone: "known",
    },
    late: {
      title: shortId(late?.id ?? "New consumer", 24),
      role: "Outside frozen inventory",
      fact: late?.receipt_state ?? "No native receipt",
      tone: "late",
    },
  };
  const [selectedKey, setSelectedKey] = useState("late");
  const selected = selections[selectedKey];

  return (
    <main className="rcp-root rcp-radar">
      <a className="rcp-radar-brand" href="/workbench">Retirement Conductor</a>
      <div className="rcp-radar-summary">
        <span>{data.evidence.sources.length} required sources complete</span>
        <strong>{data.decision}</strong>
      </div>

      <section className="rcp-radar-field" aria-label="Evidence envelope">
        <svg className="rcp-radar-lines" viewBox="0 0 1000 700" role="img" aria-label="Evidence connections around the target field">
          <ellipse className="rcp-radar-envelope" cx="500" cy="345" rx="315" ry="250" />
          <path className="rcp-radar-line rcp-radar-line-datahub" d="M500 345 C390 270 285 210 175 165" />
          <path className="rcp-radar-line rcp-radar-line-git" d="M500 345 C590 260 675 190 785 140" />
          <path className="rcp-radar-line rcp-radar-line-validation" d="M500 345 C620 430 700 500 800 565" />
          <path className="rcp-radar-line rcp-radar-line-known" d="M500 345 C410 430 330 500 240 540" />
          <path className="rcp-radar-line rcp-radar-line-late" d="M500 345 C665 350 820 350 950 345" />
          <path className="rcp-radar-lease" d="M350 112 C470 52 625 60 735 128" />
          <text x="500" y="65" textAnchor="middle">frozen evidence envelope</text>
          <text x="540" y="100">lease invalidated</text>
        </svg>

        <button className="rcp-radar-node rcp-radar-node-field" data-selected={selectedKey === "field"} type="button" onClick={() => setSelectedKey("field")}>
          <span>{fieldName(data.target)}</span>
          <small>target field</small>
        </button>
        <button className="rcp-radar-node rcp-radar-node-datahub" data-selected={selectedKey === "datahub"} type="button" onClick={() => setSelectedKey("datahub")}>
          <span>DataHub</span><small>graph</small>
        </button>
        <button className="rcp-radar-node rcp-radar-node-git" data-selected={selectedKey === "git"} type="button" onClick={() => setSelectedKey("git")}>
          <span>Git / dbt</span><small>change</small>
        </button>
        <button className="rcp-radar-node rcp-radar-node-validation" data-selected={selectedKey === "validation"} type="button" onClick={() => setSelectedKey("validation")}>
          <span>Receipt</span><small>accepted</small>
        </button>
        <button className="rcp-radar-node rcp-radar-node-known" data-selected={selectedKey === "known"} type="button" onClick={() => setSelectedKey("known")}>
          <span>Known consumer</span><small>validated</small>
        </button>
        <button className="rcp-radar-node rcp-radar-node-late" data-selected={selectedKey === "late"} type="button" onClick={() => setSelectedKey("late")}>
          <span>New consumer</span><small>no receipt</small>
        </button>
      </section>

      <aside className="rcp-radar-dock" data-tone={selected.tone} aria-live="polite">
        <div><span>{selected.role}</span><strong>{selected.title}</strong></div>
        <p>{selected.fact}</p>
        <button type="button" onClick={() => setSelectedKey("late")}>Show blocking evidence</button>
      </aside>
    </main>
  );
}

type ReviewMode = "inspect" | "propose" | "authorize" | "validate" | "reconcile";

function reviewDetail(mode: ReviewMode, data: WorkbenchView, late: Consumer | undefined) {
  switch (mode) {
    case "inspect":
      return {
        title: "Evidence scope",
        copy: data.evidence.coverage.label,
        facts: data.evidence.sources.map((source) => [source.id, `${source.status}, ${source.scope.pages ?? 0} page(s)`]),
      };
    case "propose":
      return {
        title: "Bounded change",
        copy: "Only the recorded dbt path and field substitution are in scope.",
        facts: [["Path", data.change.paths[0] ?? "Missing"], ["Mutation", `${fieldName(data.target)} to ${fieldName(data.replacement)}`]],
      };
    case "authorize":
      return {
        title: "Authorization boundary",
        copy: "A human authorization was recorded before the source mutation. The agent did not own this transition.",
        facts: [["State", "Recorded"], ["Mutation boundary", "Git branch and reviewable patch"]],
      };
    case "validate":
      return {
        title: "Native validation",
        copy: data.change.receipt ? "The accepted receipt is bound to the changed consumer and manifest." : "No accepted receipt exists.",
        facts: [["Adapter", data.change.receipt?.adapter ?? "Missing"], ["Result", data.change.receipt?.result ?? "Missing"], ["Receipt", data.change.receipt ? shortId(data.change.receipt.digest, 26) : "Missing"]],
      };
    default:
      return {
        title: "Fresh reconciliation",
        copy: data.summary.cause,
        facts: [["New consumer", late?.id ?? "Missing"], ["Disposition", late?.disposition ?? "Unknown"], ["Decision", data.decision], ["Lease", "Invalidated"]],
      };
  }
}

function NativeReview({ data }: { data: WorkbenchView }) {
  const [mode, setMode] = useState<ReviewMode>("reconcile");
  const late = data.consumers.find((consumer) => consumer.newly_observed);
  const detail = reviewDetail(mode, data, late);
  const modes: Array<{ key: ReviewMode; label: string }> = [
    { key: "inspect", label: "Inspect" },
    { key: "propose", label: "Propose" },
    { key: "authorize", label: "Authorize" },
    { key: "validate", label: "Validate" },
    { key: "reconcile", label: "Reconcile" },
  ];

  return (
    <main className="rcp-root rcp-review">
      <header className="rcp-review-toolbar">
        <a href="/workbench">Retirement Conductor</a>
        <span>{data.campaign.id}</span>
        <strong>{data.decision}</strong>
      </header>

      <nav className="rcp-review-modes" aria-label="Campaign tasks">
        {modes.map((item) => (
          <button type="button" key={item.key} aria-current={mode === item.key ? "page" : undefined} onClick={() => setMode(item.key)}>
            {item.label}
          </button>
        ))}
      </nav>

      <section className="rcp-review-editor" aria-labelledby="review-file">
        <header>
          <h1 id="review-file">{data.change.paths[0] ?? "No changed file"}</h1>
          <span>Actual retained migration patch</span>
        </header>
        <div className="rcp-review-code" role="table" aria-label="Migration diff">
          <div role="row"><span role="cell">11</span><code role="cell">select</code></div>
          <div role="row"><span role="cell">12</span><code role="cell">    order_id,</code></div>
          <div className="rcp-review-removed" role="row"><span role="cell">13</span><code role="cell">-   legacy_status as normalized_status,</code></div>
          <div className="rcp-review-added" role="row"><span role="cell">13</span><code role="cell">+   order_status as normalized_status,</code></div>
          <div role="row"><span role="cell">14</span><code role="cell">    order_total</code></div>
        </div>
        <footer>
          <div><span>Native adapter</span><strong>{data.change.receipt?.adapter ?? "Missing"}</strong></div>
          <div><span>Validation</span><strong>{data.change.receipt?.result ?? "Missing"}</strong></div>
          <div><span>Publication</span><strong>{data.publication.readback_verified ? "Read-back verified" : "Not verified"}</strong></div>
        </footer>
      </section>

      <aside className="rcp-review-context" aria-live="polite">
        <header><span>{mode}</span><h2>{detail.title}</h2></header>
        <p>{detail.copy}</p>
        <dl>
          {detail.facts.map(([label, value]) => (
            <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
          ))}
        </dl>
        {mode === "reconcile" && (
          <div className="rcp-review-refusal">
            <strong>Producer action refused</strong>
            <span>{data.primary_action.description}</span>
          </div>
        )}
      </aside>
    </main>
  );
}

export function PrototypeWorkbench({ data, variant }: { data: WorkbenchView; variant: PrototypeVariant }) {
  return (
    <>
      {variant === "operator" && <TheOperator data={data} />}
      {variant === "radar" && <EvidenceRadar data={data} />}
      {variant === "native-review" && <NativeReview data={data} />}
      <PrototypeSwitcher variant={variant} />
    </>
  );
}
