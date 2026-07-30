with expected as (
    select
        order_id,
        order_status as normalized_status,
        order_amount
    from {{ ref('orders') }}
),
differences as (
    select * from {{ ref('orders_model_00') }}
    except
    select * from expected

    union all

    select * from expected
    except
    select * from {{ ref('orders_model_00') }}
)

select * from differences
