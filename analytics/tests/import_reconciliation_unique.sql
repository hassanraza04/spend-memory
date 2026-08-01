select
  import_run_id,
  account_identity,
  currency
from {{ ref('int_import_reconciliation') }}
group by import_run_id, account_identity, currency
having count(*) > 1
