{{
  config(
    meta={
      "retirement_conductor": {
        "datahub_urn": "urn:li:dataset:(urn:li:dataPlatform:dbt,retirement_conductor.analytics.consumers.orders_model_00,PROD)"
      }
    }
  )
}}

select
    order_id,
    legacy_status as normalized_status,
    order_amount
from {{ ref('orders') }}
