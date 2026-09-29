# Test Plan: Churn Prediction & Monitoring Pipeline

Organized by layer, cheapest/fastest checks first. Work top to bottom — later
sections assume earlier ones pass.

## 1. Service health

| ID | Test | Steps | Expected result | Priority |
|----|------|-------|------------------|----------|
| H-1 | prediction-service alive | `curl http://localhost:8001/docs` | 200, FastAPI docs page loads | High |
| H-2 | data-ingestion-service alive | `curl http://localhost:8002/docs` | 200, docs page loads | High |
| H-3 | training-service alive | `curl http://localhost:8003/docs` | 200, docs page loads | High |
| H-4 | monitoring-service alive | `curl http://localhost:8004/docs` | 200, docs page loads | High |
| H-5 | prediction-service metadata loaded | `curl http://localhost:8001/churn_predictor/metadata` | Returns threshold, feature_columns, model_version — not empty/null | High |
| H-6 | Env vars resolved correctly | `docker-compose exec monitoring-service env \| grep SERVICE_URL` (repeat for training-service) | Values match compose file's internal service names, not localhost | High |

## 2. UI → monitoring-service (upload and trigger)

| ID | Test | Steps | Expected result | Priority |
|----|------|-------|------------------|----------|
| U-1 | Basic trigger succeeds | Open `monitoring_control.html`, upload a valid CSV, click Run monitoring | UI shows severity badge + metrics, no console errors | High |
| U-2 | CORS configured correctly | Same as U-1, check browser dev tools Network tab | Response has `Access-Control-Allow-Origin` header, no CORS error in console | High |
| U-3 | Missing file, button stays disabled | Load page, do not select a file | Run monitoring button remains disabled | Low |
| U-4 | Malformed/non-CSV upload | Upload a non-CSV file | Server returns a clear 4xx error; UI shows it in the error box, not a blank failure | Medium |
| U-5 | Missing required feature column | Upload a CSV missing one of `feature_columns` | Server rejects with a specific "missing feature X" message, not a generic 500 | High |

## 3. Cross-service data flow (the real proof, not just "UI showed something")

| ID | Test | Steps | Expected result | Priority |
|----|------|-------|------------------|----------|
| D-1 | Prediction reaches Snowflake | After U-1, query `SELECT * FROM PREDICTIONS ORDER BY score_at DESC LIMIT 5` in Snowflake | New rows present, correct week, correct record_ids | High |
| D-2 | Drift scores written | Query `SELECT * FROM DRIFT_LOG WHERE week = <latest>` | One row per continuous feature for that week | High |
| D-3 | Performance log written | Query `SELECT * FROM PERFORMANCE_LOG WHERE week = <latest>` | Row present, severity matches what UI displayed | High |
| D-4 | Feature snapshot written | Query `SELECT * FROM FEATURE_SNAPSHOTS WHERE week = <latest>` | Matches the uploaded batch's feature values | High |
| D-5 | Week auto-increments | Upload two separate batches back to back | Second batch gets `week = first_week + 1`, not a repeat or collision | High |
| D-6 | Re-upload doesn't corrupt week sequence | Upload the same file twice | Each upload still gets its own new, distinct week number | Medium |

## 4. Drift detection — sensitivity and specificity

| ID | Test | Steps | Expected result | Priority |
|----|------|-------|------------------|----------|
| S-1 | Clean batch → OK | Upload an unmodified, representative batch | Severity = `OK` | High |
| S-2 | Mild shift → WARNING | Upload a batch with one feature shifted ~0.5–1.0 std from baseline | Severity = `[WARNING]` | Medium |
| S-3 | Strong shift → ALERT/CRITICAL | Upload a batch with one feature shifted >1.5 std (e.g., spike `CustServCalls`) | Severity = `[ALERT]` or `[CRITICAL]`, and `DRIFT_LOG` shows elevated score only for that feature | High |
| S-4 | Specificity — untouched features stay quiet | Same as S-3 | All *other* features' drift scores in `DRIFT_LOG` remain near baseline (not falsely flagged) | High |
| S-5 | Partial coverage handled | Upload a batch where some records have no resolved `Churn` yet | `Performance` is partial/null for unresolved rows; `coverage` % reflects only resolved subset, not 100% | Medium |

## 5. Retrain & promotion flow

| ID | Test | Steps | Expected result | Priority |
|----|------|-------|------------------|----------|
| R-1 | 8-week CRITICAL streak triggers recommendation | Upload 8 consecutive drifted batches | `retrain_recommended: true` appears in the 8th week's report | High |
| R-2 | Fewer than 8 doesn't trigger | Upload only 5 consecutive CRITICAL batches | `retrain_recommended` stays false | High |
| R-3 | Non-consecutive CRITICAL doesn't trigger | Insert one clean (OK) batch in the middle of a CRITICAL streak | Streak resets; `retrain_recommended` stays false | High |
| R-4 | /train produces a sane recommendation | `curl -X POST http://localhost:8003/training_service/train` | Response includes champion vs. candidate F2/precision/recall/Brier, plus candidate threshold | High |
| R-5 | Second /train while one is pending | Call `/train` twice without promoting/rejecting in between | Second call returns `409 Conflict`, doesn't silently overwrite the pending candidate | High |
| R-6 | /promote updates everything atomically | Call `/promote` after a `/train` | `prediction-service`'s `/metadata` reflects new `model_version`, `threshold`, `baseline_stats` all at once | High |
| R-7 | /predict reflects the promoted model | Call `/predict` right after R-6 | Predictions differ from pre-promotion values (confirms in-memory model actually reloaded, not just the file on disk) | High |
| R-8 | Post-promotion validation fires | After R-6, check monitoring-service logs | Confirms `training-service` called `monitoring-service`'s run/validation endpoint | Medium |
| R-9 | Reject leaves champion untouched | Call `/train`, then reject instead of promoting | `/metadata` on prediction-service is completely unchanged; candidate files cleaned up | High |

## 6. Resilience / restart behavior

| ID | Test | Steps | Expected result | Priority |
|----|------|-------|------------------|----------|
| X-1 | prediction-service survives restart | `docker-compose restart prediction-service`, then call `/predict` | Loads the currently-promoted model from its own persisted artifact, not the original pre-promotion one | High |
| X-2 | No service crashes on the others' absence at startup | `docker-compose up` from a clean state | No `ConnectionRefusedError` tracebacks — confirms fetches happen at request time, not import time | High |
| X-3 | monitoring-service handles data-ingestion-service being briefly down | Stop data-ingestion-service mid-test, trigger a run | Clear error surfaced (ideally with retry), not an unhandled crash | Medium |

## Notes

- Run Section 1 after every `docker-compose up --build` — cheapest signal that something structural broke.
- Sections 4 and 5 are the tests that actually validate the project's core value (drift detection, safe model governance) — don't skip these in favor of only checking the UI looks right.
- For S-2/S-3, reuse the same shift-injection technique from `validate_drift_detection.py`'s original experiments rather than hand-crafting new test data each time.
