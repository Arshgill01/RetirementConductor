"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { PrototypeWorkbench, isPrototypeVariant } from "./workbench-prototypes";

export type Stage = {
  key: string;
  label: string;
  number: string;
  status: "complete" | "current" | "pending" | "invalidated";
  occurred_at: string | null;
};

export type Consumer = {
  id: string;
  disposition: string;
  closed: boolean;
  receipt_digest: string | null;
  receipt_state: string;
  newly_observed: boolean;
};

export type EvidenceSource = {
  id: string;
  required: boolean;
  status: string;
  identity: string;
  version: string;
  scope: {
    direction: string;
    max_hops: number | null;
    pages: number | null;
    reported_total: number | null;
    returned_total: number | null;
  };
  freshness: {
    observed_at: string;
    source_updated_at: string;
    maximum_age_seconds: number | null;
  };
  limitations: string[];
};

export type WorkbenchView = {
  mode: "live-local" | "read-only" | "recorded-evidence";
  campaign: { id: string; name: string; state: string };
  target: string;
  replacement: string;
  decision: string;
  decision_label: string;
  summary: { headline: string; cause: string };
  stages: Stage[];
  primary_action: {
    kind: "runtime" | "navigate";
    operation?: "inventory" | "reconcile";
    view?: ViewName;
    label: string;
    description: string;
    enabled: boolean;
  };
  consumers: Consumer[];
  new_consumer_ids: string[];
  change: {
    paths: string[];
    receipt: null | {
      consumer_id: string;
      accepted_at: string;
      digest: string;
      adapter: string;
      result: string;
    };
  };
  evidence: {
    mode: string;
    captured_at: string;
    coverage: { state: string; label: string };
    sources: EvidenceSource[];
  };
  publication: { recorded: boolean; readback_verified: boolean };
  blockers: Array<{
    code: string;
    message: string;
    recovery_action: string;
  }>;
  activity: Array<{
    sequence: number;
    event_type: string;
    occurred_at: string;
    event_digest: string;
  }>;
  generated_at: string;
  manifest_digest: string;
};

type ViewName = "overview" | "consumers" | "change" | "evidence" | "activity";

const API_BASE =
  process.env.NEXT_PUBLIC_RETIREMENT_CONDUCTOR_API_URL ??
  "http://127.0.0.1:8765";

const views: Array<{ key: Exclude<ViewName, "overview">; label: string }> = [
  { key: "consumers", label: "Consumers" },
  { key: "change", label: "Change" },
  { key: "evidence", label: "Evidence" },
  { key: "activity", label: "Activity" },
];

async function fetchWorkbench(): Promise<WorkbenchView> {
  const response = await fetch(`${API_BASE}/api/workbench`, {
    cache: "no-store",
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.message ?? payload.error ?? "Request failed.");
  }
  return payload;
}

async function fetchInitialWorkbench(): Promise<WorkbenchView> {
  try {
    return await fetchWorkbench();
  } catch {
    const response = await fetch("/workbench-recorded.json", { cache: "no-store" });
    if (!response.ok) throw new Error("The local runtime is unavailable.");
    return response.json();
  }
}

function shortDigest(value: string) {
  return value.length > 24 ? `${value.slice(0, 17)}…${value.slice(-6)}` : value;
}

function humanizeEvent(value: string) {
  return value.toLowerCase().replaceAll("_", " ");
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "UTC",
  }).format(date);
}

function Lineage({ data }: { data: WorkbenchView }) {
  const known = data.consumers.filter((consumer) => !consumer.newly_observed);
  const newlyObserved = data.consumers.filter(
    (consumer) => consumer.newly_observed,
  );
  return (
    <figure className="rcw-lineage" aria-labelledby="lineage-caption">
      <figcaption id="lineage-caption">Field lineage · focused fragment</figcaption>
      <div className="rcw-lineage-grid">
        <div className="rcw-node rcw-node-source">
          <span className="rcw-node-label">Legacy field</span>
          <strong>{data.target.split(".").at(-1)}</strong>
          <small>{data.target.split(".").slice(0, -1).join(".")}</small>
        </div>
        <div className="rcw-branch rcw-branch-known" aria-hidden="true" />
        <div className="rcw-consumer-group">
          <span className="rcw-node-label">Known consumers</span>
          {known.length ? (
            known.map((consumer) => (
              <div className="rcw-consumer-row" key={consumer.id}>
                <strong>{consumer.id}</strong>
                <span>{consumer.disposition.toLowerCase()}</span>
              </div>
            ))
          ) : (
            <div className="rcw-consumer-row">None recorded</div>
          )}
        </div>
        <div className="rcw-branch rcw-branch-target" aria-hidden="true" />
        <div className="rcw-node rcw-node-target">
          <span className="rcw-node-label">Replacement field</span>
          <strong>{data.replacement.split(".").at(-1)}</strong>
        </div>
        {newlyObserved.length > 0 && (
          <>
            <div className="rcw-branch rcw-branch-new" aria-hidden="true" />
            <div className="rcw-new-consumer">
              <span className="rcw-node-label">Newly observed</span>
              {newlyObserved.map((consumer) => (
                <strong key={consumer.id}>{consumer.id}</strong>
              ))}
            </div>
            <div className="rcw-broken-branch" aria-hidden="true" />
            <p className="rcw-broken-copy">
              <strong>Open branch</strong>
              Introduced after the frozen inventory.
            </p>
          </>
        )}
      </div>
    </figure>
  );
}

function DetailView({ name, data }: { name: ViewName; data: WorkbenchView }) {
  if (name === "consumers") {
    return (
      <section className="rcw-detail" aria-labelledby="consumers-title">
        <header>
          <p>Known scope</p>
          <h2 id="consumers-title">Consumers</h2>
        </header>
        <div className="rcw-record-list">
          {data.consumers.map((consumer) => (
            <article key={consumer.id} className="rcw-record">
              <div>
                <span>{consumer.newly_observed ? "Newly observed" : "Recorded"}</span>
                <h3>{consumer.id}</h3>
              </div>
              <dl>
                <div>
                  <dt>Disposition</dt>
                  <dd>{consumer.disposition}</dd>
                </div>
                <div>
                  <dt>Native evidence</dt>
                  <dd>{consumer.receipt_state}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      </section>
    );
  }
  if (name === "change") {
    return (
      <section className="rcw-detail" aria-labelledby="change-title">
        <header>
          <p>Bounded mutation</p>
          <h2 id="change-title">Change</h2>
        </header>
        <div className="rcw-prose-grid">
          <div>
            <h3>Authorized paths</h3>
            {data.change.paths.length ? (
              data.change.paths.map((path) => <code key={path}>{path}</code>)
            ) : (
              <p>No change plan has been recorded.</p>
            )}
          </div>
          <div>
            <h3>Change receipt</h3>
            {data.change.receipt ? (
              <dl className="rcw-facts">
                <div>
                  <dt>Adapter</dt>
                  <dd>{data.change.receipt.adapter}</dd>
                </div>
                <div>
                  <dt>Result</dt>
                  <dd>{data.change.receipt.result}</dd>
                </div>
                <div>
                  <dt>Digest</dt>
                  <dd title={data.change.receipt.digest}>
                    {shortDigest(data.change.receipt.digest)}
                  </dd>
                </div>
              </dl>
            ) : (
              <p>No native receipt has been accepted.</p>
            )}
          </div>
        </div>
      </section>
    );
  }
  if (name === "evidence") {
    return (
      <section className="rcw-detail" aria-labelledby="evidence-title">
        <header>
          <p>{data.evidence.coverage.state.replaceAll("_", " ")}</p>
          <h2 id="evidence-title">Evidence</h2>
        </header>
        <p className="rcw-lede">{data.evidence.coverage.label}</p>
        <div className="rcw-record-list">
          {data.evidence.sources.map((source) => (
            <article className="rcw-record" key={source.id}>
              <div>
                <span>{source.required ? "Required source" : "Optional source"}</span>
                <h3>{source.id}</h3>
              </div>
              <dl>
                <div>
                  <dt>Status</dt>
                  <dd>{source.status}</dd>
                </div>
                <div>
                  <dt>Observed</dt>
                  <dd>{formatTimestamp(source.freshness.observed_at)} UTC</dd>
                </div>
                <div>
                  <dt>Pagination</dt>
                  <dd>
                    {source.scope.returned_total ?? "?"} /{" "}
                    {source.scope.reported_total ?? "?"} over{" "}
                    {source.scope.pages ?? "?"} page(s)
                  </dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
        <footer className="rcw-digest">
          Manifest <span title={data.manifest_digest}>{shortDigest(data.manifest_digest)}</span>
        </footer>
      </section>
    );
  }
  return (
    <section className="rcw-detail" aria-labelledby="activity-title">
      <header>
        <p>Append-only history</p>
        <h2 id="activity-title">Activity</h2>
      </header>
      <ol className="rcw-activity">
        {data.activity.map((event) => (
          <li key={event.event_digest}>
            <time dateTime={event.occurred_at}>
              {formatTimestamp(event.occurred_at)} UTC
            </time>
            <strong>{humanizeEvent(event.event_type)}</strong>
            <span title={event.event_digest}>{shortDigest(event.event_digest)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function WorkbenchClient() {
  const searchParams = useSearchParams();
  const [data, setData] = useState<WorkbenchView | null>(null);
  const [view, setView] = useState<ViewName>("overview");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setData(await fetchWorkbench());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The local runtime is unavailable.");
    }
  }

  useEffect(() => {
    let active = true;
    fetchInitialWorkbench()
      .then((payload) => {
        if (active) setData(payload);
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(
            cause instanceof Error
              ? cause.message
              : "The local runtime is unavailable.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, []);

  async function runPrimaryAction() {
    if (!data) return;
    const action = data.primary_action;
    if (action.kind === "navigate") {
      setView(action.view ?? "overview");
      return;
    }
    if (!action.operation || !action.enabled) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/workbench/action`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Retirement-Conductor-Action": action.operation,
        },
        body: JSON.stringify({ operation: action.operation }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.message ?? payload.error ?? "Operation refused.");
      setData(payload.view);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Operation refused.");
    } finally {
      setBusy(false);
    }
  }

  if (!data) {
    return (
      <main className="rcw-connect">
        <p>Retirement Workbench</p>
        <h1>{error ? "The local campaign is not connected." : "Reading canonical state…"}</h1>
        {error && (
          <>
            <p>{error}</p>
            <button type="button" onClick={() => void load()}>
              Try again
            </button>
          </>
        )}
      </main>
    );
  }

  const prototypeVariant = searchParams.get("variant");
  if (isPrototypeVariant(prototypeVariant)) {
    return <PrototypeWorkbench data={data} variant={prototypeVariant} />;
  }

  return (
    <main className="rcw-shell">
      <a className="rcw-skip" href="#workbench-content">
        Skip to Campaign
      </a>
      <header className="rcw-topbar">
        <button type="button" className="rcw-wordmark" onClick={() => setView("overview")}>
          Retirement Workbench
        </button>
        <p>
          <span>Campaign</span>
          <strong>{data.target}</strong>
          <b aria-hidden="true">→</b>
          <strong>{data.replacement.split(".").at(-1)}</strong>
        </p>
        {data.mode === "recorded-evidence" ? (
          <button
            type="button"
            className="rcw-mode rcw-mode-button"
            onClick={() => void load()}
          >
            Recorded evidence · connect live
          </button>
        ) : (
          <span className="rcw-mode">
            {data.mode === "live-local" ? "Live local" : "Read only"}
          </span>
        )}
      </header>

      <aside className="rcw-stages" aria-label="Campaign stages">
        <ol>
          {data.stages.map((stage) => (
            <li key={stage.key} data-status={stage.status}>
              <span>{stage.number}</span>
              <strong>{stage.label}</strong>
              <i aria-hidden="true" />
            </li>
          ))}
        </ol>
      </aside>

      <section className="rcw-canvas" id="workbench-content">
        {view === "overview" ? (
          <>
            <header className="rcw-hero">
              <p>{data.stages.find((stage) => stage.status === "current")?.label}</p>
              <h1>{data.summary.headline}</h1>
              <dl>
                <div>
                  <dt>Status</dt>
                  <dd data-decision={data.decision}>{data.decision}</dd>
                </div>
                <div>
                  <dt>Exact cause</dt>
                  <dd>{data.summary.cause}</dd>
                </div>
                <div>
                  <dt>Field</dt>
                  <dd>
                    {data.target.split(".").at(-1)} <span aria-hidden="true">→</span>{" "}
                    {data.replacement.split(".").at(-1)}
                  </dd>
                </div>
              </dl>
            </header>
            <Lineage data={data} />
            <div className="rcw-action-row">
              <button
                type="button"
                onClick={() => void runPrimaryAction()}
                disabled={busy || !data.primary_action.enabled}
                aria-busy={busy}
              >
                {busy ? "Working…" : data.primary_action.label}
              </button>
              <p>{data.primary_action.description}</p>
            </div>
          </>
        ) : (
          <DetailView name={view} data={data} />
        )}
        <span className="rcw-visually-hidden" role="status" aria-live="polite">
          {busy ? `${data.primary_action.label} in progress` : ""}
        </span>
        {error && <p className="rcw-error" role="alert">{error}</p>}
      </section>

      <nav className="rcw-subnav" aria-label="Campaign details">
        {views.map((item) => (
          <button
            type="button"
            key={item.key}
            aria-current={view === item.key ? "page" : undefined}
            onClick={() => setView(item.key)}
          >
            {item.label}
          </button>
        ))}
      </nav>
    </main>
  );
}
