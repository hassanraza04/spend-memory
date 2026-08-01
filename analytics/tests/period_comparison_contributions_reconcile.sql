select
  account_identity,
  currency,
  period_start
from {{ ref('mart_period_comparisons') }}
group by 1, 2, 3
having sum(difference_net_amount_minor) <> max(observed_period_difference_minor)
