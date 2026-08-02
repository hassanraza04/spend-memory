select
  candidate_key as recurring_group_id,
  normalized_descriptor as recurring_group_label,
  enrichment_version
from {{ source('spend_memory', 'recurring_candidates') }}
where status = 'candidate'
