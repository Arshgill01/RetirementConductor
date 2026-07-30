select {{ project_status('legacy_status') }} from {{ ref('orders') }}
