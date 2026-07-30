"""Plain-language terminal and HTML views of one canonical campaign manifest."""

# ruff: noqa: E501

from __future__ import annotations

import html
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import verify_digest
from retirement_conductor.schemas import validate_schema
from retirement_conductor.vocabulary import ConsumerDisposition, Decision

_CLOSED_DISPOSITIONS = frozenset(
    {
        ConsumerDisposition.VALIDATED,
        ConsumerDisposition.REMOVED,
        ConsumerDisposition.NOT_APPLICABLE,
    }
)
_SENSITIVE_TEXT = re.compile(
    r"(?:"
    r"(?:/home/|/Users/|[A-Za-z]:\\\\)"
    r"|(?:https?://|urn:li:)"
    r"|(?:\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b)"
    r"|(?:\b(?:select|insert|update|delete|merge)\b.+\b(?:from|into|set)\b)"
    r"|(?:\b(?:token|secret|password|cookie)\b\s*[=:])"
    r")",
    re.IGNORECASE,
)

_DECISION_COPY: dict[str, tuple[str, str]] = {
    Decision.READY_TO_RETIRE: (
        "Permitted within the recorded evidence envelope",
        "Prepare one short-lived producer plan and run the gate immediately "
        "before the producer change.",
    ),
    Decision.REVIEW_REQUIRED: (
        "Accountable review is required",
        "Resolve the recorded review requirement, preserve any residual risk, "
        "then reconcile and evaluate again.",
    ),
    Decision.BLOCKED: (
        "Required proof or authority is missing",
        "Resolve the blocking evidence or authorization, then resume at the "
        "step named below.",
    ),
    Decision.UNSAFE: (
        "A known consumer or changed condition makes retirement unsafe",
        "Migrate or resolve every unsafe consumer, validate in its native "
        "system, then reconcile again.",
    ),
}

_RECOVERY_BY_PREFIX: tuple[tuple[str, str, str], ...] = (
    (
        "EVIDENCE_",
        "evidence envelope",
        "Refresh or restore the required source, verify complete pagination "
        "and freshness, then inventory or reconcile again.",
    ),
    (
        "IDENTITY_",
        "native identity mapping",
        "Resolve exactly one native object for the consumer before planning a change.",
    ),
    (
        "AUTH_",
        "authorization record",
        "Review the exact plan and record a fresh, target-bound authorization.",
    ),
    (
        "SOURCE_",
        "source-native precondition",
        "Reread the source, preserve any intervening owner change, and create "
        "a new plan from current state.",
    ),
    (
        "SCOPE_",
        "authorized target scope",
        "Reduce the proposed change to the exact allowlist and authorize a new plan.",
    ),
    (
        "APPLY_",
        "native apply result",
        "Discover the actual native state before retrying or compensating.",
    ),
    (
        "VALIDATION_",
        "source-native validator",
        "Fix the native validation failure and obtain a new passing receipt.",
    ),
    (
        "COMPENSATION_",
        "source-native recovery",
        "Resolve the recovery conflict in the source system without overwriting "
        "an intervening owner change.",
    ),
    (
        "RECONCILIATION_",
        "fresh reconciliation",
        "Refresh equivalent evidence scope and reconcile the complete observed set again.",
    ),
    (
        "POLICY_",
        "campaign policy",
        "Resolve the named consumer state or policy input, then evaluate again.",
    ),
    (
        "INTEGRITY_",
        "campaign integrity check",
        "Stop mutation, restore the canonical artifact or event stream, and reverify it.",
    ),
    (
        "RUNTIME_",
        "campaign runtime",
        "Restore the named local runtime boundary, then resume from durable state.",
    ),
    (
        "GATE_",
        "producer-side gate",
        "Do not retire the field; repair the named gate precondition and issue "
        "a new short-lived plan.",
    ),
)


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: object) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return list(value)
    return []


def _safe_public_text(value: object, fallback: str) -> str:
    text = str(value).strip()
    if not text or _SENSITIVE_TEXT.search(text):
        return fallback
    return text


def _field_identity(value: Mapping[str, Any], *, public: bool, legacy: bool) -> str:
    if public:
        return "legacy field" if legacy else "replacement field"
    parts = [
        str(value[key]).strip()
        for key in ("database", "schema", "table", "field")
        if value.get(key) not in (None, "")
    ]
    if parts:
        return ".".join(parts)
    return "unresolved field identity"


def _source_coverage(sources: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    required = [source for source in sources if source.get("required") is True]
    complete = [
        source for source in required if str(source.get("status")) == "COMPLETE"
    ]
    gaps = [source for source in required if source not in complete]
    if not required:
        state = "UNKNOWN"
        label = "Unknown — no required source is recorded"
    elif gaps:
        state = "INCOMPLETE"
        label = (
            f"Incomplete — {len(gaps)} of {len(required)} required sources "
            "are missing, stale, or partial"
        )
    elif mode != "live":
        state = "NON_LIVE"
        label = f"Bounded {mode or 'unknown'} evidence — not acceptable as live proof"
    else:
        state = "BOUNDED_COMPLETE"
        label = (
            f"Complete within declared scope — {len(complete)} of "
            f"{len(required)} required sources"
        )
    return {
        "state": state,
        "label": label,
        "required": len(required),
        "complete": len(complete),
        "gaps": len(gaps),
    }


def _blocker_explanation(blocker: Mapping[str, Any], *, public: bool) -> dict[str, str]:
    code = str(blocker.get("code") or "UNKNOWN_BLOCKER")
    message = str(blocker.get("message") or "A blocking condition is recorded.")
    if public:
        message = _safe_public_text(message, "A blocking condition is recorded.")
    for prefix, source, recovery in _RECOVERY_BY_PREFIX:
        if code.startswith(prefix):
            return {
                "code": code,
                "message": message,
                "evidence_source": source,
                "recovery_action": recovery,
            }
    return {
        "code": code,
        "message": message,
        "evidence_source": "canonical campaign state",
        "recovery_action": (
            "Inspect the canonical event history and resolve this condition "
            "before continuing."
        ),
    }


def _source_view(
    source: Mapping[str, Any],
    *,
    index: int,
    public: bool,
) -> dict[str, Any]:
    scope = _mapping(source.get("scope"))
    freshness = _mapping(source.get("freshness"))
    limitations = [str(item) for item in _sequence(source.get("limitations"))]
    if public:
        source_id = f"declared-source-{index}"
        identity = "withheld from public export"
        version = "withheld from public export"
        limitations = [
            _safe_public_text(
                item,
                "A source limitation is recorded in the private manifest.",
            )
            for item in limitations
        ]
    else:
        source_id = str(source.get("id") or f"source-{index}")
        identity = str(source.get("identity") or "not recorded")
        version = str(source.get("source_version") or "not recorded")
    return {
        "id": source_id,
        "required": source.get("required") is True,
        "status": str(source.get("status") or "UNKNOWN"),
        "identity": identity,
        "version": version,
        "scope": {
            "direction": str(scope.get("direction") or "not recorded"),
            "max_hops": scope.get("max_hops"),
            "pages": scope.get("pages"),
            "reported_total": scope.get("reported_total"),
            "returned_total": scope.get("returned_total"),
        },
        "freshness": {
            "observed_at": str(freshness.get("observed_at") or "not recorded"),
            "source_updated_at": str(
                freshness.get("source_updated_at") or "not reported"
            ),
            "maximum_age_seconds": freshness.get("maximum_age_seconds"),
        },
        "limitations": limitations
        or ["No source-specific limitation was recorded in this manifest."],
    }


def _consumer_view(
    consumer: Mapping[str, Any],
    *,
    index: int,
    public: bool,
    target: str,
    replacement: str,
) -> dict[str, Any]:
    disposition = str(consumer.get("disposition") or "UNRESOLVED")
    digest_value = consumer.get("receipt_digest")
    receipt_digest = str(digest_value) if digest_value else None
    if disposition == ConsumerDisposition.STALE:
        receipt_state = "STALE — recorded receipt is not acceptable now"
    elif disposition == ConsumerDisposition.VALIDATED and receipt_digest:
        receipt_state = "VALIDATED — native receipt accepted at manifest time"
    elif receipt_digest:
        receipt_state = "RECORDED — receipt does not close the current state"
    else:
        receipt_state = "MISSING — no accepted native validation receipt"
    consumer_id = (
        f"consumer-{index:03d}"
        if public
        else str(consumer.get("id") or f"consumer-{index:03d}")
    )
    return {
        "id": consumer_id,
        "disposition": disposition,
        "closed": disposition in _CLOSED_DISPOSITIONS,
        "receipt_digest": receipt_digest,
        "receipt_state": receipt_state,
        "native_action": f"{target} → {replacement}",
    }


def build_campaign_view(
    manifest: Mapping[str, Any],
    *,
    public: bool = False,
) -> dict[str, Any]:
    """Verify and reduce one canonical manifest into shared display fields."""

    value = dict(manifest)
    validate_schema("campaign-manifest", value)
    verify_digest(value, "manifest_digest")

    campaign = _mapping(value["campaign"])
    envelope = _mapping(value["evidence_envelope"])
    mode = str(envelope.get("mode") or "missing")
    raw_sources = [_mapping(source) for source in _sequence(envelope.get("sources"))]
    sources = [
        _source_view(source, index=index, public=public)
        for index, source in enumerate(raw_sources, start=1)
    ]
    coverage = _source_coverage(raw_sources, mode)
    target = _field_identity(_mapping(value["target"]), public=public, legacy=True)
    replacement = _field_identity(
        _mapping(value["replacement"]),
        public=public,
        legacy=False,
    )
    raw_consumers = [_mapping(consumer) for consumer in _sequence(value["consumers"])]
    consumers = [
        _consumer_view(
            consumer,
            index=index,
            public=public,
            target=target,
            replacement=replacement,
        )
        for index, consumer in enumerate(raw_consumers, start=1)
    ]
    decision = str(value["decision"])
    decision_copy = _DECISION_COPY.get(
        decision,
        (
            "Unknown campaign decision",
            "Stop and inspect the canonical campaign state.",
        ),
    )
    blockers = [
        _blocker_explanation(_mapping(blocker), public=public)
        for blocker in _sequence(value["blockers"])
    ]
    publication = _mapping(value.get("publication"))
    publication_verified = publication.get("readback_verified") is True
    if decision == Decision.READY_TO_RETIRE and not publication_verified:
        next_action = (
            "Publish and verify the campaign summary, then prepare one short-lived "
            "producer plan and run the gate."
        )
    else:
        next_action = decision_copy[1]
    counts = {
        "consumers": len(consumers),
        "closed": sum(consumer["closed"] is True for consumer in consumers),
        "open": sum(consumer["closed"] is not True for consumer in consumers),
        "blockers": len(blockers),
        "receipts": sum(
            consumer["receipt_digest"] is not None for consumer in consumers
        ),
    }
    return {
        "schema_version": "1.0.0",
        "export_mode": "public" if public else "local",
        "campaign": {
            "id": (
                "public-campaign"
                if public
                else str(campaign.get("id") or "unknown-campaign")
            ),
            "name": (
                "Public retirement campaign"
                if public
                else str(campaign.get("name") or "Unnamed campaign")
            ),
            "state": str(campaign.get("state") or "UNKNOWN"),
        },
        "target": target,
        "replacement": replacement,
        "decision": decision,
        "decision_label": decision_copy[0],
        "counts": counts,
        "evidence": {
            "mode": mode,
            "captured_at": str(envelope.get("captured_at") or "not recorded"),
            "coverage": coverage,
            "sources": sources,
        },
        "blockers": blockers,
        "consumers": consumers,
        "publication": {
            "recorded": bool(publication),
            "readback_verified": publication_verified,
        },
        "next_action": next_action,
        "generated_at": str(value["generated_at"]),
        "manifest_digest": str(value["manifest_digest"]),
        "history": [
            {
                "sequence": item.get("sequence"),
                "event_type": str(item.get("event_type") or "UNKNOWN_EVENT"),
                "event_digest": str(item.get("event_digest") or ""),
            }
            for item in (
                _mapping(event) for event in _sequence(value["transition_history"])
            )
        ],
    }


def render_campaign_inspect(view: Mapping[str, Any]) -> str:
    """Render the concise first-screen terminal summary."""

    campaign = _mapping(view["campaign"])
    counts = _mapping(view["counts"])
    evidence = _mapping(view["evidence"])
    coverage = _mapping(evidence["coverage"])
    lines = [
        str(campaign["name"]),
        f"Decision: {view['decision']} — {view['decision_label']}",
        f"Change: {view['target']} → {view['replacement']}",
        (
            "Consumers: "
            f"{counts['consumers']} total, {counts['closed']} closed, "
            f"{counts['open']} open"
        ),
        f"Blockers: {counts['blockers']}",
        f"Evidence: {coverage['label']} (mode: {evidence['mode']})",
        f"Next action: {view['next_action']}",
        f"Manifest digest: {view['manifest_digest']}",
    ]
    return "\n".join(lines)


def render_campaign_explain(view: Mapping[str, Any]) -> str:
    """Render evidence, blockers, consumers, and recovery actions as plain text."""

    lines = [render_campaign_inspect(view), "", "Evidence sources"]
    for source_value in _sequence(_mapping(view["evidence"]).get("sources")):
        source = _mapping(source_value)
        scope = _mapping(source["scope"])
        freshness = _mapping(source["freshness"])
        lines.extend(
            [
                (
                    f"- {source['id']}: {source['status']}; "
                    f"{'required' if source['required'] else 'optional'}; "
                    f"{scope['returned_total']} of {scope['reported_total']} "
                    f"reported results over {scope['pages']} pages"
                ),
                (
                    f"  Freshness: observed {freshness['observed_at']}; "
                    f"source updated {freshness['source_updated_at']}"
                ),
            ]
        )
        lines.extend(
            f"  Limitation: {limitation}"
            for limitation in _sequence(source["limitations"])
        )

    lines.extend(["", "Consumers"])
    for consumer_value in _sequence(view["consumers"]):
        consumer = _mapping(consumer_value)
        lines.append(
            f"- {consumer['id']}: {consumer['disposition']}; "
            f"{consumer['receipt_state']}"
        )
        lines.append(f"  Native change: {consumer['native_action']}")
        if consumer["receipt_digest"]:
            lines.append(f"  Receipt: {consumer['receipt_digest']}")

    lines.extend(["", "Blockers and recovery"])
    blockers = _sequence(view["blockers"])
    if not blockers:
        lines.append("- None within the recorded evidence envelope.")
    for blocker_value in blockers:
        blocker = _mapping(blocker_value)
        lines.extend(
            [
                f"- {blocker['code']}: {blocker['message']}",
                f"  Evidence source: {blocker['evidence_source']}",
                f"  Recovery: {blocker['recovery_action']}",
            ]
        )
    return "\n".join(lines)


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _status_class(value: object) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return normalized or "unknown"


def _render_source(source: Mapping[str, Any]) -> str:
    scope = _mapping(source["scope"])
    freshness = _mapping(source["freshness"])
    limitations = "".join(
        f"<li>{_escape(item)}</li>" for item in _sequence(source["limitations"])
    )
    return f"""
        <article class="ledger-row source-row">
          <div>
            <h3>{_escape(source["id"])}</h3>
            <p class="status-text status-{_status_class(source["status"])}">
              {_escape(source["status"])}
              · {"required" if source["required"] else "optional"}
            </p>
          </div>
          <dl class="source-facts">
            <div><dt>Observed</dt><dd>{_escape(freshness["observed_at"])}</dd></div>
            <div><dt>Source updated</dt><dd>{_escape(freshness["source_updated_at"])}</dd></div>
            <div><dt>Pagination</dt><dd>{_escape(scope["pages"])} pages; {_escape(scope["returned_total"])} of {_escape(scope["reported_total"])} reported</dd></div>
            <div><dt>Traversal</dt><dd>{_escape(scope["direction"])}; {_escape(scope["max_hops"])} hops</dd></div>
          </dl>
          <details>
            <summary>Scope identity, version, and limitations</summary>
            <dl class="detail-list">
              <div><dt>Identity</dt><dd>{_escape(source["identity"])}</dd></div>
              <div><dt>Version</dt><dd>{_escape(source["version"])}</dd></div>
            </dl>
            <ul class="limitations">{limitations}</ul>
          </details>
        </article>"""


def _render_consumer(consumer: Mapping[str, Any]) -> str:
    receipt = (
        f"<code>{_escape(consumer['receipt_digest'])}</code>"
        if consumer["receipt_digest"]
        else "No receipt digest"
    )
    return f"""
        <li class="ledger-row consumer-row">
          <div class="consumer-heading">
            <h3>{_escape(consumer["id"])}</h3>
            <strong class="status-text status-{_status_class(consumer["disposition"])}">
              {_escape(consumer["disposition"])}
            </strong>
          </div>
          <p>{_escape(consumer["receipt_state"])}</p>
          <dl class="detail-list">
            <div><dt>Native change</dt><dd>{_escape(consumer["native_action"])}</dd></div>
            <div><dt>Receipt</dt><dd>{receipt}</dd></div>
          </dl>
        </li>"""


def _render_blocker(blocker: Mapping[str, Any]) -> str:
    return f"""
        <li class="ledger-row blocker-row">
          <h3><code>{_escape(blocker["code"])}</code></h3>
          <p>{_escape(blocker["message"])}</p>
          <dl class="detail-list">
            <div><dt>Evidence source</dt><dd>{_escape(blocker["evidence_source"])}</dd></div>
            <div><dt>Safe recovery</dt><dd>{_escape(blocker["recovery_action"])}</dd></div>
          </dl>
        </li>"""


def render_campaign_html(view: Mapping[str, Any]) -> str:
    """Render one self-contained deterministic campaign report."""

    campaign = _mapping(view["campaign"])
    counts = _mapping(view["counts"])
    evidence = _mapping(view["evidence"])
    coverage = _mapping(evidence["coverage"])
    blockers = [_mapping(item) for item in _sequence(view["blockers"])]
    sources = [_mapping(item) for item in _sequence(evidence["sources"])]
    consumers = [_mapping(item) for item in _sequence(view["consumers"])]
    history = [_mapping(item) for item in _sequence(view["history"])]
    publication = _mapping(view["publication"])

    source_html = "".join(_render_source(source) for source in sources)
    if not source_html:
        source_html = (
            '<p class="empty-state">No evidence sources are recorded. '
            "Coverage is unknown.</p>"
        )
    blocker_html = "".join(_render_blocker(blocker) for blocker in blockers)
    if not blocker_html:
        blocker_html = (
            '<li class="empty-state">No blockers are recorded within this '
            "evidence envelope.</li>"
        )
    consumer_html = "".join(_render_consumer(consumer) for consumer in consumers)
    if not consumer_html:
        consumer_html = (
            '<li class="empty-state">No consumers are recorded. An empty '
            "inventory is not proof of absence.</li>"
        )
    history_html = "".join(
        (
            "<li>"
            f"<span>{_escape(item['sequence'])}</span>"
            f"<strong>{_escape(item['event_type'])}</strong>"
            f"<code>{_escape(item['event_digest'])}</code>"
            "</li>"
        )
        for item in history
    )
    publication_label = (
        "Verified by read-back"
        if publication["readback_verified"]
        else ("Recorded, not verified" if publication["recorded"] else "Not recorded")
    )
    return f"""<!doctype html>
<html lang="en" data-export="{_escape(view["export_mode"])}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
  <title>{_escape(campaign["name"])} · Retirement Conductor</title>
  <style>
    :root {{
      color-scheme: light;
      --paper: #f4f0e6;
      --paper-raised: #fffdf7;
      --ink: #20231f;
      --muted: #5b625b;
      --line: #b9b6a9;
      --strong-line: #6b6f67;
      --safe: #245b41;
      --warning: #8a5a13;
      --danger: #943f32;
      --focus: #6b3e1f;
      --measure: 78rem;
      font-family: "Atkinson Hyperlegible Next", "Atkinson Hyperlegible", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    html {{ background: var(--paper); color: var(--ink); }}
    body {{ margin: 0; font-size: 1rem; line-height: 1.55; }}
    a {{ color: inherit; text-underline-offset: .18em; }}
    a:focus-visible, summary:focus-visible {{
      outline: 3px solid var(--focus);
      outline-offset: 3px;
    }}
    .skip-link {{
      background: var(--ink);
      color: var(--paper-raised);
      left: 1rem;
      padding: .6rem .8rem;
      position: fixed;
      top: -5rem;
      z-index: 10;
    }}
    .skip-link:focus {{ top: 1rem; }}
    header, main, footer {{
      margin-inline: auto;
      max-width: var(--measure);
      padding-inline: clamp(1rem, 4vw, 3rem);
    }}
    header {{ padding-block: clamp(2rem, 6vw, 5rem) 2rem; }}
    .campaign-line {{
      align-items: baseline;
      border-bottom: 1px solid var(--strong-line);
      display: flex;
      gap: 1rem;
      justify-content: space-between;
      padding-bottom: .75rem;
    }}
    h1, h2, h3, p {{ margin-top: 0; }}
    h1 {{ font-size: clamp(1.8rem, 5vw, 3.5rem); letter-spacing: -.04em; line-height: 1.02; max-width: 18ch; }}
    h2 {{ font-size: 1.35rem; letter-spacing: -.015em; margin-bottom: 1rem; }}
    h3 {{ font-size: 1rem; margin-bottom: .25rem; overflow-wrap: anywhere; }}
    code {{
      font-family: "Berkeley Mono", "IBM Plex Mono", ui-monospace, monospace;
      font-size: .82em;
      overflow-wrap: anywhere;
    }}
    nav ul {{ display: flex; flex-wrap: wrap; gap: .5rem 1.25rem; list-style: none; margin: 1rem 0 0; padding: 0; }}
    .decision {{
      border-bottom: 6px solid var(--strong-line);
      display: grid;
      gap: 1.5rem;
      grid-template-columns: minmax(0, 1.6fr) minmax(16rem, .8fr);
      padding-block: 2rem;
    }}
    .decision-value {{ font-size: clamp(1.35rem, 3vw, 2.2rem); font-weight: 750; line-height: 1.15; }}
    .decision-code {{ color: var(--muted); font-family: "Berkeley Mono", "IBM Plex Mono", ui-monospace, monospace; margin-bottom: .4rem; }}
    .change-line {{ font-size: 1.1rem; margin-bottom: 0; overflow-wrap: anywhere; }}
    .next-action {{ border-left: 4px solid var(--warning); padding-left: 1rem; }}
    .next-action strong {{ display: block; margin-bottom: .25rem; }}
    .facts {{
      border-bottom: 1px solid var(--strong-line);
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      margin: 0;
    }}
    .facts div {{ border-right: 1px solid var(--line); padding: 1rem; }}
    .facts div:last-child {{ border-right: 0; }}
    dt {{ color: var(--muted); font-size: .85rem; }}
    dd {{ margin: .2rem 0 0; overflow-wrap: anywhere; }}
    .facts dd {{ font-size: 1.15rem; font-weight: 700; }}
    section {{ border-bottom: 1px solid var(--strong-line); padding-block: 2rem; scroll-margin-top: 1rem; }}
    .scope-warning {{
      background: #ede4cf;
      border-left: 5px solid var(--warning);
      margin-bottom: 2rem;
      padding: 1rem;
    }}
    .scope-warning p:last-child {{ margin-bottom: 0; }}
    .ledger-row {{ border-top: 1px solid var(--line); padding-block: 1.1rem; }}
    .source-row {{ display: grid; gap: 1rem; grid-template-columns: minmax(10rem, .6fr) minmax(0, 1.4fr); }}
    .source-row details {{ grid-column: 1 / -1; }}
    .source-facts, .detail-list {{ display: grid; gap: .65rem 1.25rem; grid-template-columns: repeat(2, minmax(0, 1fr)); margin: 0; }}
    summary {{ cursor: pointer; font-weight: 700; padding-block: .25rem; }}
    .limitations {{ margin-bottom: 0; padding-left: 1.25rem; }}
    .status-text {{ font-weight: 750; }}
    .status-complete, .status-validated, .status-ready-to-retire {{ color: var(--safe); }}
    .status-stale, .status-failed, .status-unsafe, .status-incomplete {{ color: var(--danger); }}
    .status-partial, .status-unknown, .status-blocked, .status-review-required {{ color: var(--warning); }}
    .consumer-list, .blocker-list {{ list-style: none; margin: 0; padding: 0; }}
    .consumer-heading {{ align-items: baseline; display: flex; gap: 1rem; justify-content: space-between; }}
    .empty-state {{ border-top: 1px solid var(--line); color: var(--muted); padding-block: 1rem; }}
    .history-list {{ list-style: none; margin: 0; padding: 0; }}
    .history-list li {{ border-top: 1px solid var(--line); display: grid; gap: .75rem; grid-template-columns: 3rem minmax(12rem, .6fr) minmax(0, 1.4fr); padding-block: .65rem; }}
    footer {{ color: var(--muted); padding-block: 2rem 4rem; }}
    footer p {{ margin-bottom: .4rem; overflow-wrap: anywhere; }}
    @media (max-width: 44rem) {{
      .campaign-line {{ align-items: flex-start; flex-direction: column; gap: .25rem; }}
      .decision {{ grid-template-columns: 1fr; }}
      .facts {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .facts div:nth-child(2) {{ border-right: 0; }}
      .facts div:nth-child(-n+2) {{ border-bottom: 1px solid var(--line); }}
      .source-row {{ grid-template-columns: 1fr; }}
      .source-facts, .detail-list {{ grid-template-columns: 1fr; }}
      .consumer-heading {{ align-items: flex-start; flex-direction: column; gap: .25rem; }}
      .history-list li {{ grid-template-columns: 2rem minmax(0, 1fr); }}
      .history-list code {{ grid-column: 1 / -1; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{ scroll-behavior: auto !important; transition: none !important; }}
    }}
    @media print {{
      :root {{ --paper: #fff; --paper-raised: #fff; }}
      nav, .skip-link {{ display: none; }}
      details {{ display: block; }}
      details > * {{ display: block; }}
      header, main, footer {{ max-width: none; padding-inline: 0; }}
    }}
  </style>
</head>
<body>
  <a class="skip-link" href="#main">Skip to campaign evidence</a>
  <header>
    <div class="campaign-line">
      <strong>Retirement Conductor</strong>
      <span>Campaign {_escape(campaign["id"])}</span>
    </div>
    <h1>{_escape(campaign["name"])}</h1>
    <nav aria-label="Campaign report">
      <ul>
        <li><a href="#decision">Decision</a></li>
        <li><a href="#evidence">Evidence</a></li>
        <li><a href="#consumers">Consumers</a></li>
        <li><a href="#blockers">Blockers</a></li>
        <li><a href="#history">History</a></li>
      </ul>
    </nav>
  </header>
  <main id="main">
    <section id="decision" aria-labelledby="decision-heading">
      <div class="decision">
        <div>
          <p class="decision-code">{_escape(view["decision"])}</p>
          <h2 id="decision-heading" class="decision-value">{_escape(view["decision_label"])}</h2>
          <p class="change-line">{_escape(view["target"])} → {_escape(view["replacement"])}</p>
        </div>
        <p class="next-action"><strong>Required next action</strong>{_escape(view["next_action"])}</p>
      </div>
      <dl class="facts">
        <div><dt>Consumers</dt><dd>{_escape(counts["consumers"])}</dd></div>
        <div><dt>Closed</dt><dd>{_escape(counts["closed"])}</dd></div>
        <div><dt>Open</dt><dd>{_escape(counts["open"])}</dd></div>
        <div><dt>Blockers</dt><dd>{_escape(counts["blockers"])}</dd></div>
      </dl>
    </section>
    <section id="evidence" aria-labelledby="evidence-heading">
      <h2 id="evidence-heading">Evidence envelope</h2>
      <div class="scope-warning">
        <p><strong>{_escape(coverage["label"])}</strong></p>
        <p>Mode: {_escape(evidence["mode"])}. Captured: {_escape(evidence["captured_at"])}. This report never claims visibility beyond the sources and limitations listed here.</p>
      </div>
      {source_html}
    </section>
    <section id="consumers" aria-labelledby="consumers-heading">
      <h2 id="consumers-heading">Consumer inventory and native receipts</h2>
      <ol class="consumer-list">{consumer_html}</ol>
    </section>
    <section id="blockers" aria-labelledby="blockers-heading">
      <h2 id="blockers-heading">Blockers and safe recovery</h2>
      <ul class="blocker-list">{blocker_html}</ul>
    </section>
    <section id="history" aria-labelledby="history-heading">
      <h2 id="history-heading">Canonical campaign history</h2>
      <p>DataHub publication: <strong>{_escape(publication_label)}</strong>.</p>
      <ol class="history-list">{history_html}</ol>
    </section>
  </main>
  <footer>
    <p>Canonical state generated {_escape(view["generated_at"])}</p>
    <p>Manifest digest <code>{_escape(view["manifest_digest"])}</code></p>
    <p>Export mode: {_escape(view["export_mode"])}</p>
  </footer>
</body>
</html>
"""


def write_campaign_report(
    manifest: Mapping[str, Any],
    output: Path,
    *,
    public: bool = False,
) -> dict[str, Any]:
    """Write one deterministic, self-contained HTML report."""

    view = build_campaign_view(manifest, public=public)
    content = render_campaign_html(view)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8", newline="\n")
    return {
        "result": "REPORT_BUILT",
        "campaign_id": _mapping(view["campaign"])["id"],
        "decision": view["decision"],
        "manifest_digest": view["manifest_digest"],
        "export_mode": view["export_mode"],
        "output": str(output),
    }


def safe_report_filename(campaign_id: str) -> str:
    """Return a traversal-free report filename for one campaign identifier."""

    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", campaign_id).strip(".-")
    return f"{normalized or 'campaign'}.html"
