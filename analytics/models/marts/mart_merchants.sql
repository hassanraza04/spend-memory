select
  merchant_id,
  merchant_name,
  'v1' as enrichment_version
from {{ source('spend_memory', 'merchants') }}
