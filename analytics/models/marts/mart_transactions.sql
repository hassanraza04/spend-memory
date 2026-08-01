select
  transactions.raw_transaction_id,
  transactions.import_run_id,
  transactions.document_id,
  transactions.original_filename,
  transactions.parser_id,
  transactions.parser_version,
  transactions.source_ordinal,
  transactions.source_page,
  transactions.source_row,
  transactions.source_text,
  transactions.extraction_method,
  transactions.extraction_confidence,
  transactions.date_text,
  transactions.description_text,
  transactions.amount_text,
  transactions.normalized_amount_text,
  transactions.currency_text,
  transactions.raw_account_identity,
  transactions.raw_account_reference,
  transactions.raw_balance_text,
  transactions.transaction_date,
  transactions.description,
  transactions.account_identity,
  transactions.currency,
  transactions.amount_minor,
  transactions.direction,
  transactions.net_amount_minor,
  cast(null as varchar) as merchant_id,
  cast(null as varchar) as category_id,
  cast(null as varchar) as recurring_group_id,
  'unavailable' as enrichment_version
from {{ ref('stg_transactions') }} as transactions
join {{ ref('int_import_reconciliation') }} as reconciliation
  on transactions.import_run_id = reconciliation.import_run_id
  and transactions.account_identity = reconciliation.account_identity
  and transactions.currency = reconciliation.currency
where transactions.is_valid
  and reconciliation.reconciliation_status = 'reconciled'
