select order_id, legacy_status, order_status
from {{ ref('orders') }}
where legacy_status is distinct from order_status
