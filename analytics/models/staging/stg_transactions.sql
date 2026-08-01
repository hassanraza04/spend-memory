with parser_rows as (
  select * from {{ ref('stg_canonical_csv_transactions') }}
  union all select * from {{ ref('stg_synthetic_aed_pdf_transactions') }}
  union all select * from {{ ref('stg_synthetic_pkr_pdf_transactions') }}
), parsed as (
  select *,
    {{ parsed_amount("coalesce(normalized_amount_text, amount_text)") }} as parsed_amount
  from parser_rows
), evaluated as (
  select *,
    try_strptime(date_text, '%Y-%m-%d')::date as transaction_date,
    trim(description_text) as description,
    upper(trim(currency_text)) as currency,
    {{ amount_is_integer("coalesce(normalized_amount_text, amount_text)", "parsed_amount") }}
      as amount_is_valid
  from parsed
)
select * exclude (parsed_amount),
  raw_account_identity as account_identity,
  case when transaction_date is not null and description <> '' and currency in ('AED', 'PKR')
            and amount_is_valid and raw_account_identity is not null and trim(raw_account_identity) <> ''
       then {{ amount_minor("parsed_amount") }} end as amount_minor,
  case when transaction_date is not null and description <> '' and currency in ('AED', 'PKR')
            and amount_is_valid and raw_account_identity is not null and trim(raw_account_identity) <> ''
       then {{ direction("parsed_amount") }} end as direction,
  case when transaction_date is not null and description <> '' and currency in ('AED', 'PKR')
            and amount_is_valid and raw_account_identity is not null and trim(raw_account_identity) <> ''
       then case when {{ direction("parsed_amount") }} = 'debit'
                 then -{{ amount_minor("parsed_amount") }}
                 else {{ amount_minor("parsed_amount") }} end end as net_amount_minor,
  case when transaction_date is not null and description <> '' and currency in ('AED', 'PKR')
            and amount_is_valid and raw_account_identity is not null and trim(raw_account_identity) <> ''
       then true else false end as is_valid
from evaluated
