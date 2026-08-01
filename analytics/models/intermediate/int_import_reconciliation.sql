with source as (
  select
    import_run_id,
    original_filename,
    account_identity,
    currency,
    coalesce(sum(net_amount_minor), 0)::bigint as net_amount_minor
  from {{ ref('stg_transactions') }}
  group by import_run_id, original_filename, account_identity, currency
), balance as (
  select
    import_run_id,
    account_identity,
    bool_or(balance_check_status = 'fail') as has_failed_balance_check
  from {{ ref('int_running_balance_checks') }}
  group by import_run_id, account_identity
)
select
  source.*,
  control.expected_net_amount_minor,
  coalesce(balance.has_failed_balance_check, false) as has_failed_balance_check,
  case
    when control.expected_net_amount_minor is null then 'not_available'
    when source.net_amount_minor <> control.expected_net_amount_minor then 'unreconciled'
    when coalesce(balance.has_failed_balance_check, false) then 'unreconciled'
    else 'reconciled'
  end as reconciliation_status
from source
left join {{ ref('import_controls') }} as control
  on source.original_filename = control.original_filename
  and source.account_identity = control.account_identity
  and source.currency = control.currency
left join balance
  on source.import_run_id = balance.import_run_id
  and source.account_identity = balance.account_identity
