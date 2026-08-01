with parser_rows as (
  select * from {{ ref('stg_canonical_csv_transactions') }}
  union all select * from {{ ref('stg_synthetic_aed_pdf_transactions') }}
  union all select * from {{ ref('stg_synthetic_pkr_pdf_transactions') }}
), evaluated as (
  select *,
    try_strptime(date_text, '%Y-%m-%d')::date as transaction_date,
    trim(description_text) as description,
    upper(trim(currency_text)) as currency,
    {{ amount_is_integer("coalesce(normalized_amount_text, amount_text)") }} as amount_is_valid
  from parser_rows
)
select *,
  raw_account_identity as account_identity,
  case when transaction_date is not null and description <> '' and currency in ('AED', 'PKR')
            and amount_is_valid and raw_account_identity is not null and trim(raw_account_identity) <> ''
       then {{ amount_minor("coalesce(normalized_amount_text, amount_text)") }} end as amount_minor,
  case when transaction_date is not null and description <> '' and currency in ('AED', 'PKR')
            and amount_is_valid and raw_account_identity is not null and trim(raw_account_identity) <> ''
       then {{ direction("coalesce(normalized_amount_text, amount_text)") }} end as direction,
  case when transaction_date is not null and description <> '' and currency in ('AED', 'PKR')
            and amount_is_valid and raw_account_identity is not null and trim(raw_account_identity) <> ''
       then case when {{ direction("coalesce(normalized_amount_text, amount_text)") }} = 'debit'
                 then -{{ amount_minor("coalesce(normalized_amount_text, amount_text)") }}
                 else {{ amount_minor("coalesce(normalized_amount_text, amount_text)") }} end end as net_amount_minor,
  case when transaction_date is not null and description <> '' and currency in ('AED', 'PKR')
            and amount_is_valid and raw_account_identity is not null and trim(raw_account_identity) <> ''
       then true else false end as is_valid
from evaluated
