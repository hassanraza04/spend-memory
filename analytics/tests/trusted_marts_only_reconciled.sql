select transactions.raw_transaction_id
from {{ ref('mart_transactions') }} as transactions
join {{ ref('int_import_reconciliation') }} as reconciliation
  on transactions.import_run_id = reconciliation.import_run_id
  and transactions.account_identity = reconciliation.account_identity
  and transactions.currency = reconciliation.currency
where reconciliation.reconciliation_status <> 'reconciled'
