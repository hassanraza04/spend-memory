{% macro active_raw_transactions() %}
select
  raw.raw_transaction_id,
  raw.import_run_id,
  run.document_id,
  document.original_filename,
  run.parser_id,
  run.parser_version,
  raw.source_ordinal,
  raw.date_text,
  raw.description_text,
  raw.amount_text,
  raw.normalized_amount_text,
  raw.currency_text,
  raw.source_page,
  raw.source_row,
  raw.source_text,
  raw.extraction_method,
  raw.raw_account_identity,
  raw.raw_account_reference,
  raw.raw_balance_text,
  raw.extraction_confidence
from {{ source('spend_memory', 'raw_transactions') }} as raw
join {{ source('spend_memory', 'import_runs') }} as run on raw.import_run_id = run.run_id
join {{ source('spend_memory', 'source_documents') }} as document on run.document_id = document.document_id
where run.is_active = true
{% endmacro %}
