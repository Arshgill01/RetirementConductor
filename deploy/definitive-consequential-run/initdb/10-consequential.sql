\set ON_ERROR_STOP on
\getenv observer_password RC_CP05_OBSERVER_PASSWORD
\getenv mutation_password RC_CP05_MUTATION_PASSWORD
\getenv superset_password RC_CP05_SUPERSET_PASSWORD
\getenv legacy_password RC_CP05_LEGACY_PASSWORD
\getenv replacement_password RC_CP05_REPLACEMENT_PASSWORD

CREATE ROLE rc_cp05_observer LOGIN PASSWORD :'observer_password';
CREATE ROLE rc_cp05_mutator LOGIN PASSWORD :'mutation_password';
CREATE ROLE rc_cp05_superset LOGIN PASSWORD :'superset_password';
CREATE ROLE rc_cp05_legacy_reader LOGIN PASSWORD :'legacy_password';
CREATE ROLE rc_cp05_replacement_reader LOGIN PASSWORD :'replacement_password';

CREATE SCHEMA retirement_lab AUTHORIZATION rc_cp05_mutator;
SET ROLE rc_cp05_mutator;
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
RESET ROLE;

GRANT CONNECT ON DATABASE retirement_consequential
  TO rc_cp05_observer, rc_cp05_mutator, rc_cp05_superset,
     rc_cp05_legacy_reader, rc_cp05_replacement_reader;
GRANT USAGE ON SCHEMA retirement_lab
  TO rc_cp05_observer, rc_cp05_superset,
     rc_cp05_legacy_reader, rc_cp05_replacement_reader;
GRANT SELECT ON retirement_lab.orders
  TO rc_cp05_observer, rc_cp05_superset,
     rc_cp05_legacy_reader, rc_cp05_replacement_reader;
