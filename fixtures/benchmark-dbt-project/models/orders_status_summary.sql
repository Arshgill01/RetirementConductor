{{
  config(
    meta={
      "retirement_conductor": {
        "datahub_urn": "urn:li:dataset:(urn:li:dataPlatform:dbt,retirement_benchmark.analytics.consumers.orders_status_summary,PROD)"
      }
    }
  )
}}

select
    order_id,
    legacy_status as normalized_status,
    total_amount
from {{ ref('orders') }}
