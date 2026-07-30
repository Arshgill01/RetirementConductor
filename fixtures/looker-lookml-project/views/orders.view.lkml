view: orders {
  sql_table_name: analytics.commerce.orders ;;

  dimension: id {
    primary_key: yes
    type: number
    sql: ${TABLE}.id ;;
  }

  dimension: legacy_status {
    type: string
    sql: ${TABLE}.legacy_status ;;
  }

  dimension: order_status {
    type: string
    sql: ${TABLE}.order_status ;;
  }
}
