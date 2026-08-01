with active_runs as (
  select
    run.run_id as import_run_id,
    document.original_filename
  from {{ source('spend_memory', 'import_runs') }} as run
  join {{ source('spend_memory', 'source_documents') }} as document
    on run.document_id = document.document_id
  where run.is_active = true
), transaction_totals as (
  select
    import_run_id,
    account_identity,
    currency,
    coalesce(sum(net_amount_minor), 0)::bigint as net_amount_minor
  from {{ ref('stg_transactions') }}
  group by import_run_id, account_identity, currency
), source as (
  select
    active_runs.import_run_id,
    active_runs.original_filename,
    transaction_totals.account_identity,
    transaction_totals.currency,
    coalesce(transaction_totals.net_amount_minor, 0)::bigint as net_amount_minor
  from active_runs
  left join transaction_totals
    on active_runs.import_run_id = transaction_totals.import_run_id
), balance as (
  select
    import_run_id,
    account_identity,
    currency,
    bool_or(balance_check_status = 'fail') as has_failed_balance_check
  from {{ ref('int_running_balance_checks') }}
  group by import_run_id, account_identity, currency
)
select
  source.*,
  control.expected_net_amount_minor,
  coalesce(balance.has_failed_balance_check, false) as has_failed_balance_check,
  case
    when source.account_identity is null or source.currency is null then 'not_available'
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
  and source.currency = balance.currency
