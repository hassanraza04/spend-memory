with transactions as (
  select *,
    regexp_replace(
      lower(trim(regexp_replace(description, '\s+(pos|app|online|station|cafe|pharm)$', '', 'i'))),
      '[^a-z0-9]',
      '',
      'g'
    ) as normalized_description
  from {{ ref('stg_transactions') }}
)
select
  first.raw_transaction_id as first_raw_transaction_id,
  second.raw_transaction_id as second_raw_transaction_id,
  first.import_run_id,
  first.account_identity,
  first.currency,
  first.transaction_date,
  first.amount_minor,
  first.normalized_description,
  100 as candidate_score,
  'same_date_same_amount_same_description' as candidate_reason
from transactions as first
join transactions as second
  on first.account_identity = second.account_identity
  and first.currency = second.currency
  and first.amount_minor = second.amount_minor
  and first.transaction_date = second.transaction_date
  and first.normalized_description = second.normalized_description
  and first.raw_transaction_id < second.raw_transaction_id
