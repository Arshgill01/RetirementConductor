with expected as (
    select
        order_id,
        order_status as normalized_status,
        order_amount
    from {{ ref('orders_isolated') }}
),
differences as (
    select * from {{ ref('orders_isolated_model') }}
    except
    select * from expected

    union all

    select * from expected
    except
    select * from {{ ref('orders_isolated_model') }}
)

select * from differences
