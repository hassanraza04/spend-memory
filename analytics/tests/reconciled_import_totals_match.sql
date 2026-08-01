select *
from {{ ref('int_import_reconciliation') }}
where reconciliation_status = 'reconciled'
  and expected_net_amount_minor is not null
  and net_amount_minor <> expected_net_amount_minor
