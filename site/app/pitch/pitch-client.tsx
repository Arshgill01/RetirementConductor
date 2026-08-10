"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

const slideCount = 3;

function clampSlide(value: number) {
  return Math.max(0, Math.min(slideCount - 1, value));
}

export function PitchClient() {
  const searchParams = useSearchParams();
  const [slide, setSlide] = useState(() => {
    const requested = Number.parseInt(searchParams.get("slide") ?? "1", 10);
    return Number.isFinite(requested) ? clampSlide(requested - 1) : 0;
  });
  const [controlsVisible, setControlsVisible] = useState(true);

  const move = useCallback((offset: number) => {
    setSlide((current) => clampSlide(current + offset));
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (["ArrowRight", "PageDown", " "].includes(event.key)) {
        event.preventDefault();
        move(1);
      } else if (["ArrowLeft", "PageUp"].includes(event.key)) {
        event.preventDefault();
        move(-1);
      } else if (event.key === "Home") {
        setSlide(0);
      } else if (event.key === "End") {
        setSlide(slideCount - 1);
      } else if (event.key.toLowerCase() === "h") {
        setControlsVisible((current) => !current);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [move]);

  return (
    <main className="pitch" data-slide={slide + 1}>
      <p className="pitch-wordmark">Retirement Conductor</p>
      <p className="pitch-context">legacy_status → order_status</p>

      <section
        className="pitch-slide pitch-slide-opening"
        aria-hidden={slide !== 0}
      >
        <h1>
          The new field is live.
          <span>Can we delete the old one?</span>
        </h1>
        <p className="pitch-opening-note">
          One SQL statement can break every model, dashboard, or job still
          reading orders.legacy_status.
        </p>
      </section>

      <section
        className="pitch-slide pitch-slide-datahub"
        aria-hidden={slide !== 1}
      >
        <h2>
          The repository saw <strong>one</strong> consumer.
          <span>
            DataHub found <strong>thirty-one.</strong>
          </span>
        </h2>

        <figure className="pitch-lineage">
          <figcaption>Complete, paged field lineage</figcaption>
          <div className="pitch-field">legacy_status</div>
          <div className="pitch-branch pitch-branch-known">
            <span>Git / dbt</span>
            <strong>1 known consumer</strong>
          </div>
          <div className="pitch-branch pitch-branch-graph">
            <span>DataHub</span>
            <strong>30 more consumers</strong>
          </div>
        </figure>

        <p className="pitch-proof-note">
          Live-local result · seven complete pages · bounded evidence, not a
          universal guarantee
        </p>
      </section>

      <section
        className="pitch-slide pitch-slide-method"
        aria-hidden={slide !== 2}
      >
        <h2>
          Retirement Conductor owns the path to deletion.
          <span>The latest evidence decides.</span>
        </h2>

        <ol className="pitch-flow">
          <li>
            <span>DataHub</span>
            Discover
          </li>
          <li>Change</li>
          <li>Test natively</li>
          <li>
            <span>DataHub</span>
            Recheck
          </li>
          <li className="pitch-outcome">
            <strong>Remove</strong>
            <em>or refuse</em>
          </li>
        </ol>

        <p className="pitch-method-note">
          Find every observed reader. Move and test what is authorized. Recheck
          before the database change.
        </p>
      </section>

      <nav
        className="pitch-controls"
        aria-label="Pitch slides"
        data-visible={controlsVisible}
      >
        <button
          type="button"
          onClick={() => move(-1)}
          disabled={slide === 0}
          aria-label="Previous slide"
        >
          ←
        </button>
        <span aria-live="polite">
          {String(slide + 1).padStart(2, "0")} / {String(slideCount).padStart(2, "0")}
        </span>
        <button
          type="button"
          onClick={() => move(1)}
          disabled={slide === slideCount - 1}
          aria-label="Next slide"
        >
          →
        </button>
      </nav>

      <p className="pitch-help" data-visible={controlsVisible}>
        arrows or space · H hides controls
      </p>
    </main>
  );
}
