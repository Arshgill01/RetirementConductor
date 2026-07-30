CREATE TABLE campaigns (
    campaign_id TEXT PRIMARY KEY,
    specification_digest TEXT NOT NULL,
    specification_json TEXT NOT NULL,
    state TEXT NOT NULL,
    materialized_manifest_json TEXT,
    materialized_manifest_digest TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE campaign_events (
    campaign_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_event_digest TEXT,
    event_digest TEXT NOT NULL,
    event_json TEXT NOT NULL,
    PRIMARY KEY (campaign_id, sequence),
    UNIQUE (campaign_id, idempotency_key),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE TABLE native_identity_claims (
    native_identity_digest TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    claimed_at TEXT NOT NULL,
    released_at TEXT,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE INDEX campaign_events_digest
    ON campaign_events(campaign_id, event_digest);
CREATE INDEX native_identity_claims_campaign
    ON native_identity_claims(campaign_id, released_at);
