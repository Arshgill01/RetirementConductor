{{
  config(
    meta={
      "retirement_conductor": {
        "datahub_urn": "urn:li:dataset:(urn:li:dataPlatform:dbt,retirement_conductor.analytics.consumers.orders_isolated_model,PROD)"
      }
    }
  )
}}

select
    order_id,
    legacy_status as normalized_status,
    order_amount
from {{ ref('orders_isolated') }}
