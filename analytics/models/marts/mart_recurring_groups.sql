select
  candidates.candidate_key as recurring_group_id,
  candidates.normalized_descriptor as recurring_group_label,
  candidates.enrichment_version
from {{ source('spend_memory', 'recurring_candidates') }} candidates
join {{ source('spend_memory', 'recurring_candidate_state') }} state
  on state.active_generation_id = candidates.generation_id
where candidates.status = 'candidate'
