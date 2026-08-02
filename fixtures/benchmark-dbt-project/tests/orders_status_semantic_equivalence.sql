with expected as (
    select
        order_id,
        order_status as normalized_status,
        total_amount
    from {{ ref('orders') }}
),
differences as (
    select * from {{ ref('orders_status_summary') }}
    except
    select * from expected

    union all

    select * from expected
    except
    select * from {{ ref('orders_status_summary') }}
)

select * from differences
