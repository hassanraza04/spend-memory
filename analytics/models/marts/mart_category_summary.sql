select
  transactions.account_identity,
  transactions.currency,
  transactions.category_id,
  coalesce(categories.category_label, 'uncategorized') as category_label,
  count(*) as transaction_count,
  sum(transactions.net_amount_minor)::bigint as net_amount_minor
from {{ ref('mart_transactions') }} as transactions
left join {{ ref('mart_categories') }} as categories
  on transactions.category_id = categories.category_id
group by 1, 2, 3, 4
