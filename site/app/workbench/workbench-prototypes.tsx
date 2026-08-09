"use client";

// Prototype question: which operational model makes a retirement decision easiest to understand and trust?

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { Consumer, Stage, WorkbenchView } from "./workbench-client";

const prototypeVariants = [
  { key: "cartographer", label: "Dependency Cartographer" },
  { key: "film", label: "Campaign Film" },
  { key: "control-room", label: "Change Control Room" },
] as const;

export type PrototypeVariant = (typeof prototypeVariants)[number]["key"];

export function isPrototypeVariant(value: string | null): value is PrototypeVariant {
  return prototypeVariants.some((variant) => variant.key === value);
}

function fieldName(value: string) {
  return value.split(".").at(-1) ?? value;
}

function shortId(value: string) {
  return value.length > 20 ? `${value.slice(0, 9)}…${value.slice(-6)}` : value;
}

function formatTime(value: string | null) {
  if (!value) return "—";
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
        <small>{currentIndex + 1} / {prototypeVariants.length}</small>
        {prototypeVariants[currentIndex].label}
      </span>
      <button type="button" onClick={() => select(currentIndex + 1)} aria-label="Next design">
        →
      </button>
      <a href={pathname}>Baseline</a>
    </div>
  );
}

function Cartographer({ data }: { data: WorkbenchView }) {
  const known = data.consumers.filter((consumer) => !consumer.newly_observed);
  const newlyObserved = data.consumers.filter((consumer) => consumer.newly_observed);
  const [selected, setSelected] = useState<Consumer | null>(newlyObserved[0] ?? known[0] ?? null);

  return (
    <main className="rcp-root rcp-map">
      <header className="rcp-map-header">
        <a href="/workbench">Retirement Conductor</a>
        <p>{data.campaign.id}</p>
        <strong>{data.decision}</strong>
      </header>

      <section className="rcp-map-canvas" aria-labelledby="map-title">
        <div className="rcp-map-intro">
          <span>Dependency map · fresh reconciliation</span>
          <h1 id="map-title">One new edge changed the decision.</h1>
          <p>{data.summary.cause}</p>
        </div>

        <div className="rcp-map-graph" aria-label="Focused field dependency graph">
          <div className="rcp-map-source">
            <small>Field proposed for retirement</small>
            <strong>{fieldName(data.target)}</strong>
            <span>{data.target.split(".").slice(0, -1).join(".")}</span>
          </div>

          <div className="rcp-map-known">
            <small>Known at inventory</small>
            {known.map((consumer) => (
              <button
                type="button"
                key={consumer.id}
                data-selected={selected?.id === consumer.id}
                onClick={() => setSelected(consumer)}
              >
                <i aria-hidden="true" />
                <span>{shortId(consumer.id)}</span>
                <small>{consumer.disposition}</small>
              </button>
            ))}
          </div>

          <div className="rcp-map-target">
            <small>Replacement</small>
            <strong>{fieldName(data.replacement)}</strong>
          </div>

          <div className="rcp-map-new">
            <small>Discovered at reconciliation</small>
            {newlyObserved.map((consumer) => (
              <button
                type="button"
                key={consumer.id}
                data-selected={selected?.id === consumer.id}
                onClick={() => setSelected(consumer)}
              >
                <i aria-hidden="true" />
                <span>{shortId(consumer.id)}</span>
                <small>{consumer.disposition} · no receipt</small>
              </button>
            ))}
          </div>

          <div className="rcp-map-break">
            <span>Unresolved edge</span>
          </div>
        </div>
      </section>

      <aside className="rcp-map-inspector" aria-live="polite">
        <div>
          <small>Selected consumer</small>
          <strong>{selected ? selected.id : "No consumer selected"}</strong>
        </div>
        <dl>
          <div><dt>Disposition</dt><dd>{selected?.disposition ?? "—"}</dd></div>
          <div><dt>Native evidence</dt><dd>{selected?.receipt_digest ? "Receipt accepted" : "Missing"}</dd></div>
          <div><dt>Evidence scope</dt><dd>{data.evidence.coverage.state.replaceAll("_", " ")}</dd></div>
          <div><dt>Observed</dt><dd>{formatTime(data.evidence.captured_at)} UTC</dd></div>
        </dl>
        <p>{data.primary_action.description}</p>
      </aside>
    </main>
  );
}

type FilmScene = {
  stage: Stage;
  title: string;
  copy: string;
};

function filmScene(stage: Stage, data: WorkbenchView): FilmScene {
  const scenes: Record<string, [string, string]> = {
    inventory: ["Establish the known world.", `${data.consumers.length - data.new_consumer_ids.length} consumer was captured inside the declared evidence envelope.`],
    plan: ["Change one exact path.", data.change.paths[0] ?? "No authorized path was recorded."],
    authorize: ["A human crosses the boundary.", "The agent can propose. The trusted runtime records authorization and owns the transition."],
    apply: ["The migration becomes real.", data.change.receipt ? `${data.change.receipt.adapter} applied the bounded change.` : "No applied change is recorded."],
    validate: ["Native proof, not an API success.", data.change.receipt?.result ?? "No native receipt was accepted."],
    reconcile: ["The graph changed underneath us.", data.summary.cause],
    lease: ["The permission disappears.", "No retirement action can proceed against an invalidated lease."],
  };
  const [title, copy] = scenes[stage.key] ?? [stage.label, data.summary.cause];
  return { stage, title, copy };
}

function SceneProof({ scene, data }: { scene: FilmScene; data: WorkbenchView }) {
  switch (scene.stage.key) {
    case "inventory":
      return (
        <div className="rcp-film-proof rcp-film-count">
          <strong>{data.consumers.length - data.new_consumer_ids.length}</strong>
          <span>known consumer</span>
          <small>{data.evidence.sources.length} required sources</small>
        </div>
      );
    case "plan":
    case "apply":
      return (
        <div className="rcp-film-proof rcp-film-path">
          <small>Authorized surface</small>
          <code>{data.change.paths[0] ?? "No path"}</code>
          <span>{data.change.receipt?.result ?? "PENDING"}</span>
        </div>
      );
    case "authorize":
      return (
        <div className="rcp-film-proof rcp-film-boundary">
          <span>Agent</span><i aria-hidden="true" /><strong>Human authorization</strong><i aria-hidden="true" /><span>Trusted runtime</span>
        </div>
      );
    case "validate":
      return (
        <div className="rcp-film-proof rcp-film-receipt">
          <span>Native validation receipt</span>
          <strong>{data.change.receipt?.result ?? "MISSING"}</strong>
          <code>{data.change.receipt ? shortId(data.change.receipt.digest) : "—"}</code>
        </div>
      );
    case "reconcile":
      return (
        <div className="rcp-film-proof rcp-film-reversal">
          <span>READY TO RETIRE</span>
          <i aria-hidden="true">→</i>
          <strong>{data.decision}</strong>
          <small>{shortId(data.new_consumer_ids[0] ?? "new consumer")}</small>
        </div>
      );
    default:
      return (
        <div className="rcp-film-proof rcp-film-lease">
          <small>Retirement lease</small>
          <strong>INVALIDATED</strong>
          <span>Producer action refused</span>
        </div>
      );
  }
}

function CampaignFilm({ data }: { data: WorkbenchView }) {
  const scenes = useMemo(() => data.stages.map((stage) => filmScene(stage, data)), [data]);
  const defaultIndex = Math.max(0, data.stages.findIndex((stage) => stage.status === "current"));
  const [sceneIndex, setSceneIndex] = useState(defaultIndex);
  const scene = scenes[sceneIndex];

  return (
    <main className="rcp-root rcp-film">
      <header className="rcp-film-header">
        <a href="/workbench">Retirement Conductor</a>
        <span>A campaign in seven acts</span>
        <strong>{data.mode.replaceAll("-", " ")}</strong>
      </header>

      <section className="rcp-film-stage" aria-live="polite">
        <div className="rcp-film-narrative" key={scene.stage.key}>
          <span>{scene.stage.number} / 07 · {scene.stage.label}</span>
          <h1>{scene.title}</h1>
          <p>{scene.copy}</p>
          <time dateTime={scene.stage.occurred_at ?? undefined}>{formatTime(scene.stage.occurred_at)} UTC</time>
        </div>
        <SceneProof scene={scene} data={data} />
      </section>

      <nav className="rcp-film-strip" aria-label="Campaign scenes">
        {scenes.map((item, index) => (
          <button
            type="button"
            key={item.stage.key}
            data-status={item.stage.status}
            aria-current={index === sceneIndex ? "step" : undefined}
            onClick={() => setSceneIndex(index)}
          >
            <span>{item.stage.number}</span>
            <strong>{item.stage.label}</strong>
            <small>{formatTime(item.stage.occurred_at)}</small>
          </button>
        ))}
      </nav>
    </main>
  );
}

function ControlRoom({ data }: { data: WorkbenchView }) {
  const known = data.consumers.filter((consumer) => !consumer.newly_observed);
  const newlyObserved = data.consumers.filter((consumer) => consumer.newly_observed);

  return (
    <main className="rcp-root rcp-control">
      <header className="rcp-control-header">
        <a href="/workbench">RC / Change Control</a>
        <dl>
          <div><dt>Campaign</dt><dd>{data.campaign.id}</dd></div>
          <div><dt>Evidence captured</dt><dd>{formatTime(data.evidence.captured_at)} UTC</dd></div>
          <div><dt>Sources</dt><dd>{data.evidence.sources.length} / {data.evidence.sources.length} complete</dd></div>
          <div><dt>Decision</dt><dd data-decision={data.decision}>{data.decision}</dd></div>
        </dl>
      </header>

      <section className="rcp-control-command">
        <div>
          <span>Change order</span>
          <strong>{fieldName(data.target)}</strong>
          <i aria-hidden="true">→</i>
          <strong>{fieldName(data.replacement)}</strong>
        </div>
        <p>{data.summary.headline}</p>
      </section>

      <ol className="rcp-control-track" aria-label="Campaign stages">
        {data.stages.map((stage) => (
          <li key={stage.key} data-status={stage.status}>
            <span>{stage.number}</span>
            <i aria-hidden="true" />
            <strong>{stage.label}</strong>
            <time dateTime={stage.occurred_at ?? undefined}>{formatTime(stage.occurred_at)}</time>
          </li>
        ))}
      </ol>

      <section className="rcp-control-ledger">
        <div className="rcp-control-consumers">
          <header><h1>Consumer register</h1><span>{data.consumers.length} observed</span></header>
          <div className="rcp-control-table" role="table" aria-label="Observed consumers">
            <div role="row" className="rcp-control-table-head">
              <span role="columnheader">Identity</span><span role="columnheader">Observed</span><span role="columnheader">Disposition</span><span role="columnheader">Receipt</span>
            </div>
            {[...known, ...newlyObserved].map((consumer) => (
              <div role="row" key={consumer.id} data-new={consumer.newly_observed}>
                <strong role="cell">{consumer.id}</strong>
                <span role="cell">{consumer.newly_observed ? "Reconciliation" : "Inventory"}</span>
                <span role="cell">{consumer.disposition}</span>
                <span role="cell">{consumer.receipt_digest ? "Accepted" : "Missing"}</span>
              </div>
            ))}
          </div>
        </div>

        <aside className="rcp-control-orders">
          <div className="rcp-control-stamp">
            <small>Retirement lease</small>
            <strong>INVALIDATED</strong>
            <span>Producer gate held</span>
          </div>
          <dl>
            <div><dt>Exact cause</dt><dd>{data.summary.cause}</dd></div>
            <div><dt>Recovery order</dt><dd>{data.primary_action.description}</dd></div>
            <div><dt>Publication</dt><dd>{data.publication.readback_verified ? "DataHub read-back verified" : "Not verified"}</dd></div>
            <div><dt>Manifest</dt><dd>{shortId(data.manifest_digest)}</dd></div>
          </dl>
        </aside>
      </section>
    </main>
  );
}

export function PrototypeWorkbench({ data, variant }: { data: WorkbenchView; variant: PrototypeVariant }) {
  return (
    <>
      {variant === "cartographer" && <Cartographer data={data} />}
      {variant === "film" && <CampaignFilm data={data} />}
      {variant === "control-room" && <ControlRoom data={data} />}
      <PrototypeSwitcher variant={variant} />
    </>
  );
}
