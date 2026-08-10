"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent, RefObject } from "react";

export type Stage = {
  key: string;
  label: string;
  number: string;
  status: "complete" | "current" | "pending" | "blocked";
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

type Pairing = { apiBase: string; token: string };

const DEFAULT_API_BASE = "http://127.0.0.1:8765";
const PAIRING_STORAGE_KEY = "retirement-conductor-workbench-pairing";

const views: Array<{ key: Exclude<ViewName, "overview">; label: string }> = [
  { key: "consumers", label: "Consumers" },
  { key: "change", label: "Change" },
  { key: "evidence", label: "Evidence" },
  { key: "activity", label: "Activity" },
];

function normalizeApiBase(value: string) {
  const url = new URL(value);
  if (
    !["http:", "https:"].includes(url.protocol) ||
    !["127.0.0.1", "localhost"].includes(url.hostname) ||
    url.username ||
    url.password ||
    (url.pathname !== "/" && url.pathname !== "") ||
    url.search ||
    url.hash
  ) {
    throw new Error("Use a loopback runtime URL such as http://127.0.0.1:8765.");
  }
  return url.origin;
}

async function pairedFetch(path: string, pairing: Pairing, init?: RequestInit) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 6000);
  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${pairing.token}`);
  try {
    return await fetch(`${pairing.apiBase}${path}`, {
      ...init,
      cache: "no-store",
      headers,
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timeout);
  }
}

async function responsePayload(response: Response) {
  const payload = await response.json();
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("The pairing token was rejected. Copy the current token from the runtime terminal.");
    }
    if (response.status === 403) {
      throw new Error("This site origin is not allowed by the local runtime.");
    }
    throw new Error(payload.message ?? payload.error ?? "The runtime refused the request.");
  }
  return payload;
}

async function fetchWorkbench(pairing: Pairing): Promise<WorkbenchView> {
  const response = await pairedFetch("/api/workbench", pairing);
  return responsePayload(response);
}

async function connectWorkbench(pairing: Pairing): Promise<WorkbenchView> {
  const healthResponse = await pairedFetch("/api/health", pairing);
  const health = await responsePayload(healthResponse);
  const view = await fetchWorkbench(pairing);
  if (health.campaign_id !== view.campaign.id) {
    throw new Error("The runtime health check and campaign view disagree. Connection refused.");
  }
  return view;
}

async function fetchRecordedWorkbench(): Promise<WorkbenchView> {
  const response = await fetch("/workbench-recorded.json", { cache: "no-store" });
  if (!response.ok) throw new Error("The recorded campaign evidence is unavailable.");
  return response.json();
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

function connectionMessage(cause: unknown) {
  if (cause instanceof DOMException && cause.name === "AbortError") {
    return "The loopback runtime did not respond within six seconds.";
  }
  if (cause instanceof TypeError) {
    return "The browser could not reach the loopback runtime. Start it locally and allow this site's HTTPS origin.";
  }
  return cause instanceof Error ? cause.message : "The runtime connection failed.";
}

function PairingPanel({
  apiBase,
  token,
  busy,
  error,
  tokenRef,
  onApiBaseChange,
  onTokenChange,
  onClose,
  onSubmit,
}: {
  apiBase: string;
  token: string;
  busy: boolean;
  error: string | null;
  tokenRef: RefObject<HTMLInputElement | null>;
  onApiBaseChange: (value: string) => void;
  onTokenChange: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <aside
      className="rcw-pairing"
      role="dialog"
      aria-labelledby="pairing-title"
      aria-describedby="pairing-description"
    >
      <button className="rcw-pairing-dismiss" type="button" onClick={onClose} aria-label="Close pairing panel">
        Close
      </button>
      <p>Local runtime</p>
      <h2 id="pairing-title">Pair this view to the campaign engine.</h2>
      <p className="rcw-pairing-intro" id="pairing-description">
        The campaign store, DataHub connection, and mutation authority remain on your machine.
        The ephemeral token stays in this browser tab.
      </p>
      <form onSubmit={onSubmit}>
        <label htmlFor="runtime-url">Loopback API</label>
        <input
          id="runtime-url"
          inputMode="url"
          value={apiBase}
          onChange={(event) => onApiBaseChange(event.target.value)}
          spellCheck={false}
          required
        />
        <label htmlFor="pairing-token">Pairing token</label>
        <input
          id="pairing-token"
          ref={tokenRef}
          type="password"
          value={token}
          onChange={(event) => onTokenChange(event.target.value)}
          autoComplete="off"
          spellCheck={false}
          required
        />
        <button type="submit" disabled={busy || !token.trim()} aria-busy={busy}>
          {busy ? "Pairing…" : "Pair runtime"}
        </button>
      </form>
      <p className="rcw-pairing-command">
        Start with <code>retirement-conductor workbench serve …</code>, then copy the token printed in that terminal.
      </p>
      {error && <p className="rcw-pairing-error" role="alert">{error}</p>}
    </aside>
  );
}

export function WorkbenchClient() {
  const [data, setData] = useState<WorkbenchView | null>(null);
  const [recordedData, setRecordedData] = useState<WorkbenchView | null>(null);
  const [view, setView] = useState<ViewName>("overview");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pairing, setPairing] = useState<Pairing | null>(null);
  const [pairingOpen, setPairingOpen] = useState(false);
  const [pairingBusy, setPairingBusy] = useState(false);
  const [pairingError, setPairingError] = useState<string | null>(null);
  const [apiBaseInput, setApiBaseInput] = useState(DEFAULT_API_BASE);
  const [tokenInput, setTokenInput] = useState("");
  const tokenRef = useRef<HTMLInputElement>(null);
  const pairingTriggerRef = useRef<HTMLButtonElement>(null);

  async function pairRuntime(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPairingBusy(true);
    setPairingError(null);
    try {
      const nextPairing = {
        apiBase: normalizeApiBase(apiBaseInput.trim()),
        token: tokenInput.trim(),
      };
      const nextData = await connectWorkbench(nextPairing);
      sessionStorage.setItem(PAIRING_STORAGE_KEY, JSON.stringify(nextPairing));
      setPairing(nextPairing);
      setData(nextData);
      setError(null);
      setPairingOpen(false);
      setTokenInput("");
    } catch (cause) {
      setPairingError(connectionMessage(cause));
    } finally {
      setPairingBusy(false);
    }
  }

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const recorded = await fetchRecordedWorkbench();
        if (!active) return;
        setRecordedData(recorded);
        setData(recorded);

        const saved = sessionStorage.getItem(PAIRING_STORAGE_KEY);
        if (!saved) return;
        try {
          const parsed = JSON.parse(saved) as Pairing;
          const savedPairing = {
            apiBase: normalizeApiBase(parsed.apiBase),
            token: parsed.token,
          };
          const liveData = await connectWorkbench(savedPairing);
          if (!active) return;
          setPairing(savedPairing);
          setData(liveData);
        } catch {
          sessionStorage.removeItem(PAIRING_STORAGE_KEY);
        }
      } catch (cause) {
        if (active) setError(connectionMessage(cause));
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!pairingOpen) return;
    tokenRef.current?.focus();
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setPairingOpen(false);
        pairingTriggerRef.current?.focus();
      }
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [pairingOpen]);

  function closePairing() {
    setPairingOpen(false);
    requestAnimationFrame(() => pairingTriggerRef.current?.focus());
  }

  function disconnectRuntime() {
    sessionStorage.removeItem(PAIRING_STORAGE_KEY);
    setPairing(null);
    setError(null);
    if (recordedData) setData(recordedData);
  }

  async function runPrimaryAction() {
    if (!data) return;
    const action = data.primary_action;
    if (action.kind === "navigate") {
      setView(action.view ?? "overview");
      return;
    }
    if (!action.operation || !action.enabled || !pairing) return;
    setBusy(true);
    setError(null);
    try {
      const response = await pairedFetch("/api/workbench/action", pairing, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Retirement-Conductor-Action": action.operation,
        },
        body: JSON.stringify({ operation: action.operation }),
      });
      const payload = await responsePayload(response);
      setData(payload.view);
    } catch (cause) {
      setError(connectionMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  if (!data) {
    return (
      <main className="rcw-connect">
        <p>Retirement Workbench</p>
        <h1>{error ? "The campaign evidence could not be read." : "Reading canonical state…"}</h1>
        {error && (
          <>
            <p>{error}</p>
            <button type="button" onClick={() => window.location.reload()}>
              Reload evidence
            </button>
          </>
        )}
      </main>
    );
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
            ref={pairingTriggerRef}
            onClick={() => {
              setPairingError(null);
              setPairingOpen(true);
            }}
          >
            Recorded evidence · pair local
          </button>
        ) : (
          <button type="button" className="rcw-mode rcw-mode-button" onClick={disconnectRuntime}>
            {data.mode === "live-local" ? "Live local" : "Paired read only"} · disconnect
          </button>
        )}
      </header>

      {pairingOpen && (
        <PairingPanel
          apiBase={apiBaseInput}
          token={tokenInput}
          busy={pairingBusy}
          error={pairingError}
          tokenRef={tokenRef}
          onApiBaseChange={setApiBaseInput}
          onTokenChange={setTokenInput}
          onClose={closePairing}
          onSubmit={pairRuntime}
        />
      )}

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
