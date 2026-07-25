# Hermes resale archive

This module is the local operating spine for resale items. It stores inventory outside the source repository, creates a deterministic daily action queue, and never posts or messages externally.

## Storage

Default database:

```text
%USERPROFILE%\.hermes\resale\inventory.sqlite3
```

Override the runtime data root:

```bat
set HERMES_DATA_DIR=C:\Users\max\HermesData
```

The SQLite database uses WAL mode and stores item events separately from the current item record.

## Workflow states

- `CAPTURED`: identify, photograph and price.
- `RESEARCH`: confirm the exact match and sold value.
- `READY`: approve title, price and platform.
- `POSTED`: monitor offers and prepare dispatch.
- `SOLD`: pack, send and record the result.
- `HOLD`: wait for stronger evidence or better timing.
- `FIX`: clean, repair or retake photographs.

Changing a status inside Hermes records the workflow decision only. It does not post, message, buy, sell, or dispatch anything externally.

## Local API

Start Hermes:

```bat
cd /d C:\Users\max\Hermes-oracle-llm
start-hermes.cmd
```

### Capture an item

```powershell
$body = @{
  title = "Rare soul record"
  category = "vinyl"
  priority = "HIGH"
  target_price = 120
  research_confidence = 0.8
  expected_effort_minutes = 10
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/resale/items `
  -ContentType application/json `
  -Body $body
```

### Read today's queue

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/resale/queue
```

### Read performance summary

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/resale/summary
```

The summary includes status counts, active expected value, sold value for the past day/week/month, and average sale time when posted and sold dates exist.

### Preview an import

```powershell
$payload = Get-Content .\inventory-export.json -Raw
$body = @{ payload = $payload; preview = $true } | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/resale/import/json `
  -ContentType application/json `
  -Body $body
```

Set `preview` to `false` only after reviewing the returned items.

### Export

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/resale/export/json -OutFile inventory-export.json
Invoke-WebRequest http://127.0.0.1:8000/api/resale/export/csv -OutFile inventory-export.csv
```

## Queue logic

The queue score is deterministic and uses:

- workflow readiness;
- operator priority;
- expected value;
- research confidence;
- item age;
- estimated effort.

`SOLD` and `HOLD` items are excluded. The algorithm never uses marketplace APIs or paid research services.

## Verification

```bat
python -m pytest -q tests/test_resale_archive.py tests/test_resale_api.py tests/test_backend_main.py
python -m compileall -q resale backend
```

## Current checkpoint boundaries

Included:

- durable local item schema;
- SQLite persistence and event history;
- deterministic action queue;
- local API;
- JSON/CSV export and previewed JSON import;
- day/week/month sold totals and average sale time.

Not included yet:

- photo ingestion;
- marketplace research adapters;
- listing-copy generation;
- external posting or messaging;
- packaging labels or courier integration;
- historical user-data import.
