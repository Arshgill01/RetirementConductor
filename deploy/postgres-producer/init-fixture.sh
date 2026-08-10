#!/bin/sh
set -eu

psql --set ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set observer_password="$RC_CP01_OBSERVER_PASSWORD" \
  --set mutation_password="$RC_CP01_MUTATION_PASSWORD" \
  --set unprivileged_password="$RC_CP01_UNPRIVILEGED_PASSWORD" <<'SQL'
CREATE ROLE rc_cp01_observer LOGIN PASSWORD :'observer_password';
CREATE ROLE rc_cp01_mutator LOGIN PASSWORD :'mutation_password';
CREATE ROLE rc_cp01_unprivileged LOGIN PASSWORD :'unprivileged_password';
CREATE SCHEMA retirement_lab AUTHORIZATION rc_cp01_mutator;
GRANT CONNECT ON DATABASE rc_cp01_producer
  TO rc_cp01_observer, rc_cp01_mutator, rc_cp01_unprivileged;
GRANT USAGE ON SCHEMA retirement_lab
  TO rc_cp01_observer, rc_cp01_unprivileged;
SQL

if [ "$RC_CP01_FIXTURE_VARIANT" = "replacement_type_drift" ]; then
  psql --set ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" <<'SQL'
SET ROLE rc_cp01_mutator;
CREATE TABLE retirement_lab.orders (
  order_id bigint PRIMARY KEY,
  legacy_status text NOT NULL,
  order_status integer NOT NULL,
  amount_cents bigint NOT NULL
);
INSERT INTO retirement_lab.orders VALUES (1, 'pending', 1, 1200);
RESET ROLE;
GRANT SELECT ON retirement_lab.orders
  TO rc_cp01_observer, rc_cp01_unprivileged;
SQL
else
  psql --set ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" <<'SQL'
SET ROLE rc_cp01_mutator;
CREATE TABLE retirement_lab.orders (
  order_id bigint PRIMARY KEY,
  legacy_status text NOT NULL,
  order_status text NOT NULL,
  amount_cents bigint NOT NULL
);
INSERT INTO retirement_lab.orders VALUES (1, 'pending', 'pending', 1200);
RESET ROLE;
GRANT SELECT ON retirement_lab.orders
  TO rc_cp01_observer, rc_cp01_unprivileged;
SQL
fi

if [ "$RC_CP01_FIXTURE_VARIANT" = "dependent_view" ]; then
  psql --set ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" <<'SQL'
SET ROLE rc_cp01_mutator;
CREATE VIEW retirement_lab.legacy_orders AS
SELECT order_id, legacy_status FROM retirement_lab.orders;
RESET ROLE;
SQL
fi
