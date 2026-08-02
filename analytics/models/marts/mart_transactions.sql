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
  annotation.merchant_id,
  coalesce(override.category_id, assignment.category_id) as category_id,
  cast(null as varchar) as recurring_group_id,
  coalesce(annotation.enrichment_version, 'unavailable') as enrichment_version
from {{ ref('stg_transactions') }} as transactions
join {{ ref('int_import_reconciliation') }} as reconciliation
  on transactions.import_run_id = reconciliation.import_run_id
  and transactions.account_identity = reconciliation.account_identity
  and transactions.currency = reconciliation.currency
left join {{ source('spend_memory', 'transaction_merchant_annotations') }} as annotation
  on transactions.raw_transaction_id = annotation.raw_transaction_id
  and annotation.resolution_status = 'confirmed'
left join {{ source('spend_memory', 'transaction_category_overrides') }} as override
  on transactions.raw_transaction_id = override.raw_transaction_id
left join {{ source('spend_memory', 'merchant_category_assignments') }} as assignment
  on annotation.merchant_id = assignment.merchant_id
where transactions.is_valid
  and reconciliation.reconciliation_status = 'reconciled'
