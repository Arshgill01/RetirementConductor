CREATE TABLE gate_attempts (
    attempt_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('REFUSED', 'INTENT_RECORDED', 'EXECUTED', 'OUTCOME_UNKNOWN')
    ),
    manifest_digest TEXT NOT NULL,
    decision TEXT NOT NULL,
    plan_digest TEXT,
    trusted_run_id TEXT,
    writer_id TEXT NOT NULL,
    refusal_code TEXT,
    attempt_json TEXT NOT NULL,
    attempt_digest TEXT NOT NULL,
    outcome_json TEXT,
    outcome_digest TEXT,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE UNIQUE INDEX gate_attempts_consumed_plan
    ON gate_attempts(plan_digest)
    WHERE status IN ('INTENT_RECORDED', 'EXECUTED', 'OUTCOME_UNKNOWN');

CREATE INDEX gate_attempts_campaign
    ON gate_attempts(campaign_id, recorded_at, attempt_id);
