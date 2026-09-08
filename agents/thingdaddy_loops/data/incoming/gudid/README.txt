Drop weekly GUDID / AccessGUDID delta files here (.json or .ndjson).
Accepted shapes:
  - openFDA style:  {"results": [ { "company_name": "...", "identifiers": [ {"id": "<DI/GTIN>"} ], "country": "US" }, ... ]}
  - record array:   [ { "labeler": "...", "primary_di": "<DI/GTIN>", "country": "US" }, ... ]
  - NDJSON:         one record object per line
On the next Loop A run, files here are ingested (idempotent by DI) and moved to processed/.
