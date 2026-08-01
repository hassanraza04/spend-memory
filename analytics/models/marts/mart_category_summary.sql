select
  account_identity,
  currency,
  category_id,
  coalesce(category_id, 'uncategorized') as category_label,
  count(*) as transaction_count,
  sum(net_amount_minor)::bigint as net_amount_minor
from {{ ref('mart_transactions') }}
group by 1, 2, 3, 4
