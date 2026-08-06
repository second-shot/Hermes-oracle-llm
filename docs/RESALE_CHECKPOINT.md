# Hermes resale checkpoint

This branch is the first local-only resale foundation for Hermes.

## Delivered

- durable SQLite inventory outside the source tree
- CAPTURED, RESEARCH, READY, POSTED, SOLD, HOLD and FIX states
- deterministic daily queue using readiness, urgency, value, confidence and effort
- JSON and CSV import/export
- day, week and month performance summaries
- explicit boundary: no marketplace posting, messaging, buying, selling or dispatch without operator approval

## Verification

Run:

```bat
python -m unittest tests.test_resale_archive -v
python -m compileall -q hermes_modules tests
```

## Next checkpoint

Wire the archive into the live FastAPI application and add the minimal black-and-white operator interface for item capture, queue review, approval and status changes.
