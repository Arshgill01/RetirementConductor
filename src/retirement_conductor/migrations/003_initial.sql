CREATE TABLE gate_plans (
    plan_digest TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    manifest_digest TEXT NOT NULL,
    trusted_run_id TEXT NOT NULL,
    writer_id TEXT NOT NULL,
    prepared_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE UNIQUE INDEX gate_plans_manifest
    ON gate_plans(campaign_id, manifest_digest);

CREATE UNIQUE INDEX gate_attempts_consumed_manifest
    ON gate_attempts(campaign_id, manifest_digest)
    WHERE status IN ('INTENT_RECORDED', 'EXECUTED', 'OUTCOME_UNKNOWN');
