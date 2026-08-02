select
  category_id,
  category_label,
  'v1' as enrichment_version
from {{ source('spend_memory', 'categories') }}
