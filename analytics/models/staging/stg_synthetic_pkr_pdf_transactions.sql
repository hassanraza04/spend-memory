{{ config(materialized='ephemeral') }}

select *
from ({{ active_raw_transactions() }}) as active_raw_transactions
where parser_id = 'synthetic-pkr-compact-pdf'
