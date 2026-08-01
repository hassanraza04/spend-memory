with monthly_totals as (
  select
    account_identity,
    currency,
    period_start,
    sum(net_amount_minor)::bigint as net_amount_minor
  from {{ ref('mart_monthly_summary') }}
  group by 1, 2, 3
), totals_with_previous as (
  select
    *,
    lag(period_start) over (
      partition by account_identity, currency order by period_start
    ) as previous_period_start,
    lag(net_amount_minor) over (
      partition by account_identity, currency order by period_start
    ) as previous_net_amount_minor
  from monthly_totals
), directions as (
  select direction
  from (values ('debit'), ('credit')) as values(direction)
), contribution_amounts as (
  select
    totals.account_identity,
    totals.currency,
    totals.period_start,
    directions.direction,
    coalesce(summary.net_amount_minor, 0)::bigint as net_amount_minor
  from monthly_totals as totals
  cross join directions
  left join {{ ref('mart_monthly_summary') }} as summary
    on totals.account_identity = summary.account_identity
    and totals.currency = summary.currency
    and totals.period_start = summary.period_start
    and directions.direction = summary.direction
), contributions_with_previous as (
  select
    *,
    lag(net_amount_minor) over (
      partition by account_identity, currency, direction order by period_start
    ) as previous_net_amount_minor
  from contribution_amounts
)
select
  contributions.account_identity,
  contributions.currency,
  contributions.period_start,
  totals.previous_period_start,
  contributions.direction,
  contributions.previous_net_amount_minor::bigint as before_net_amount_minor,
  contributions.net_amount_minor::bigint as after_net_amount_minor,
  (contributions.net_amount_minor - contributions.previous_net_amount_minor)::bigint
    as difference_net_amount_minor,
  (totals.net_amount_minor - totals.previous_net_amount_minor)::bigint
    as observed_period_difference_minor
from contributions_with_previous as contributions
join totals_with_previous as totals
  on contributions.account_identity = totals.account_identity
  and contributions.currency = totals.currency
  and contributions.period_start = totals.period_start
where totals.previous_net_amount_minor is not null
