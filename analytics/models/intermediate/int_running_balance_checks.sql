with parsed_balances as (
  select *,
    try_cast(regexp_replace(raw_balance_text, '[^0-9+-]', '', 'g') as bigint) as current_balance_minor
  from {{ ref('stg_transactions') }}
), adjacent_balances as (
  select *,
    lag(raw_transaction_id) over balance_window as previous_raw_transaction_id,
    lag(current_balance_minor) over balance_window as previous_balance_minor
  from parsed_balances
  window balance_window as (
    partition by import_run_id, account_identity
    order by transaction_date, source_ordinal
  )
)
select
  raw_transaction_id,
  import_run_id,
  account_identity,
  transaction_date,
  source_ordinal,
  net_amount_minor,
  raw_balance_text,
  previous_raw_transaction_id,
  previous_balance_minor,
  current_balance_minor,
  case
    when previous_balance_minor is null or current_balance_minor is null then 'not_available'
    when current_balance_minor = previous_balance_minor + net_amount_minor then 'pass'
    else 'fail'
  end as balance_check_status
from adjacent_balances
