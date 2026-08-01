select *,
  case
    when transaction_date is null then 'invalid_date'
    when description is null or description = '' then 'missing_description'
    when currency not in ('AED', 'PKR') then 'unsupported_currency'
    when amount_is_valid is not true then 'invalid_amount'
    when raw_account_identity is null or trim(raw_account_identity) = '' then 'missing_account_identity'
  end as rejection_reason
from {{ ref('stg_transactions') }}
where is_valid = false
