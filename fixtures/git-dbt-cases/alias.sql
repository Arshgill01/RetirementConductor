select legacy_status as status_alias from {{ ref('orders') }}
