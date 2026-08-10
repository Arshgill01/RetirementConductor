\set ON_ERROR_STOP on
\getenv legacy_reader_password LEGACY_READER_PASSWORD
\getenv replacement_reader_password REPLACEMENT_READER_PASSWORD

CREATE EXTENSION pgcrypto;

CREATE ROLE legacy_reader LOGIN PASSWORD :'legacy_reader_password';
CREATE ROLE replacement_reader LOGIN PASSWORD :'replacement_reader_password';

CREATE SCHEMA retirement_lab;
CREATE TABLE retirement_lab.orders (
    id integer PRIMARY KEY,
    legacy_status text NOT NULL,
    order_status text NOT NULL,
    amount_cents bigint NOT NULL
);

WITH generator AS (
    SELECT
        generated_id,
        (ARRAY['pending', 'processing', 'shipped', 'delivered'])[
            ((generated_id * 17 + 20260810) % 4) + 1
        ] AS generated_status,
        ((generated_id * 137 + 20260810) % 50000) + 100 AS generated_amount
    FROM generate_series(1, 128) AS generated_id
)
INSERT INTO retirement_lab.orders (id, legacy_status, order_status, amount_cents)
SELECT generated_id, generated_status, generated_status, generated_amount
FROM generator
ORDER BY generated_id;

GRANT CONNECT ON DATABASE native_breakage TO legacy_reader, replacement_reader;
GRANT USAGE ON SCHEMA retirement_lab TO legacy_reader, replacement_reader;
GRANT SELECT ON retirement_lab.orders TO legacy_reader, replacement_reader;
