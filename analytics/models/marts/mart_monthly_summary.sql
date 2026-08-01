select
  account_identity,
  currency,
  date_trunc('month', transaction_date)::date as period_start,
  direction,
  count(*) as transaction_count,
  sum(amount_minor)::bigint as amount_minor,
  sum(net_amount_minor)::bigint as net_amount_minor
from {{ ref('mart_transactions') }}
group by 1, 2, 3, 4
