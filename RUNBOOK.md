# Runbook: Churn Monitoring Pipeline

Operational reference for running, interpreting, and troubleshooting this
project. Written for whoever picks this up next — including future me.

## Running the system locally

```bash
docker-compose up --build
```

Confirm all four services report `Uvicorn running on http://0.0.0.0:8000`
with no tracebacks, then check each is reachable:

```
http://localhost:8001/docs   prediction-service
http://localhost:8002/docs   data-ingestion-service
http://localhost:8003/docs   training-service
http://localhost:8004/docs   monitoring-service
```

To trigger a monitoring run, either open `ui/monitoring_control.html`
directly in a browser (double-click, or serve it via
`python -m http.server` from inside `ui/`), or call the endpoint directly:

```bash
curl -X POST http://localhost:8004/churn_predictor/run -F "file=@batch.csv"
```

**One-time setup, before any of the above works:**
1. `python -m bootstrap.train_evaluate_select` — model comparison (informs
   which model gets frozen; not a runtime dependency).
2. `python -m bootstrap.train_final` — trains and freezes the model, writes
   the initial artifacts.
3. `python -m services.data_ingestion_service.scripts.setup_snowflake` —
   provisions the Snowflake schema. Requires Snowflake credentials already
   configured (see Environment setup below).
4. Copy the initial `artifacts/` output into `services/prediction_service/artifacts/`
   so the container has its own self-contained copy.

See `TEST_PLAN.md` for a full, structured set of test cases across every
layer of the system.

## Severity levels

Produced by `alert_log()`. Two signals feed the classification: **drift
score** (feature distribution vs. training baseline — always available,
computed by `monitoring-service` using stats fetched from
`prediction-service`'s `/metadata`) and **performance metrics**
(F2/precision/recall/Brier — only available once `Churn` is known for that
batch, fetched via `data-ingestion-service`).

| Severity | Meaning |
|---|---|
| `OK` | Max feature drift score \|z\| ≤ 0.5. No action needed. |
| `[WARNING]` | Max drift score in (0.5, 1.0]. Worth watching, not urgent. |
| `[ALERT]` | Max drift score > 1.0, but performance impact not yet confirmed (ground truth pending, or confirmed-but-not-degraded). |
| `[CRITICAL]` | Max drift score > 1.0 **and** current Brier loss exceeds `brier_baseline_mean + 1.5*brier_baseline_std`. Both signals agree something is wrong. |

Both thresholds were derived by checking the false-positive rate against
real baseline data, not chosen arbitrarily.

**Known caveat:** the weeks used to originally define a model's baseline
partly define the reference they're later compared against. Expect those
weeks to trend toward `OK`/`WATCH` by construction — this isn't the
monitoring "working correctly" in the same sense as a genuinely
out-of-sample week being correctly flagged.

## Champion/challenger retraining

Triggered when `monitoring-service` detects **8 consecutive** `[CRITICAL]`
weeks under the currently deployed `model_version` (checked via
`data-ingestion-service`'s `/recent-severity`, filtered by model version so
history from a previous champion is never mixed in). Non-consecutive
`CRITICAL` weeks (a clean week anywhere in the streak) reset the count.

| Endpoint | Service | Purpose |
|---|---|---|
| `POST /training_service/train` | training-service | Retrains a challenger, evaluates vs. champion, returns a recommendation. Does not touch the live model. Fails with `409` if a candidate is already pending. |
| `POST /training_service/promote` | training-service | Human-approved: atomically pushes the candidate's model + metadata to prediction-service, bumps `model_version`, triggers a fresh monitoring run to validate. |
| `POST /training_service/reject` | training-service | Discards the pending candidate; champion is left completely untouched. |

**Retraining data:** expanding window (original training pool + every
resolved week since), with the drifted period recency-weighted
(`sample_weight`, derived from row counts — not a guessed constant) so it
isn't diluted by a much larger volume of older, pre-drift history.

**Evaluation split:** temporal, not random — the candidate trains on the
earlier portion of the drift period and is evaluated on a held-out, more
recent slice it never trained on, alongside the champion on the same slice.
Random/stratified splitting would leak the drift pattern into evaluation.

**Promotion criteria:** F2 improving alone is not sufficient — recall and
Brier are checked alongside it, with tolerances derived from bootstrapping
the champion's own performance on the eval set (not fixed constants), since
F2 can improve while recall quietly regresses.

**Baseline recomputation at promotion:** the candidate's `baseline_stats`
(feature mean/std) are computed from its own full training set — including
the drifted period, since that's now the model's own definition of normal.
`brier_baseline_stats` are computed via pooled out-of-fold cross-validation
on the candidate's training set (same technique as the original model
comparison), not from the small held-out eval slice, which is too small a
sample for an ongoing reference.

## Snowflake schema quick reference

- **`PREDICTIONS`** — one row per scoring event. `record_id` + `week` +
  `probability`/`prediction`. Written every time a batch is scored,
  regardless of whether ground truth is known yet.
- **`ACTUALS`** — one row per customer, once their outcome resolves.
  `record_id` is the sole primary key. Deliberately holds no feature data.
- **`FEATURE_SNAPSHOTS`** — one row per scoring event, holding the raw
  feature values behind it. Joined with `ACTUALS` on `record_id` — that
  join *is* the expanding-window training set, growing automatically as
  outcomes resolve, no separate CSV-append logic needed.
- **`DRIFT_LOG`** — one row per (feature, week).
- **`PERFORMANCE_LOG`** — one or more rows per (week, model_version),
  append-only. `computed_at` distinguishes versions; query with
  `QUALIFY ROW_NUMBER() ...` for the latest estimate per week.

Week numbers are assigned **server-side** by `data-ingestion-service`
(`MAX(week) + 1`) at ingestion — never trusted from an uploaded file, since
client-supplied sequence numbers can't be relied on to be correct or unique.

## Known failure modes encountered during development

Kept at the pattern level — what broke, why, and the general lesson.

- **Silent leakage from shared mutable state.** An early drift-experiment
  loop reused and saved over the same DataFrame/file across supposedly
  isolated single-feature experiments, causing drift to accumulate across
  features. Caught by explicitly checking non-target features' statistics
  after each experiment, not just the targeted one.
- **Comparisons that always evaluate the same way.** A gap-detection
  function computed differences in the wrong direction for descending-sorted
  data, making every comparison silently non-positive. Caught by
  deliberately constructing a case where it *should* fire and confirming it
  did — a check never proven to catch a true positive can't be trusted.
- **Silent type coercion across library/serialization boundaries.** NumPy
  scalar types, pandas `Index` objects, and `datetime.date` objects each
  fail `json.dump()` differently. General lesson: explicitly cast to native
  Python types at the exact boundary where data leaves pandas/NumPy and
  enters JSON, whether that's a local file write or an HTTP response body.
- **Network calls at import time, not call time.** A module-level
  `metadata = get_metadata()` ran the instant the module was imported —
  meaning it fired before Compose had guaranteed the target service was
  actually listening, causing intermittent `ConnectionRefusedError` at
  startup. Fix: move any such call inside a function, invoked only when
  actually needed, never at module scope.
- **Docker build context assumptions.** Import statements written as if the
  whole monorepo were visible (`from services.training_service...`) broke
  the moment each service was built from its own isolated folder as the
  Docker build context — the fix is importing relative to what's actually
  inside that one folder (`from scripts...`), which also serves as a
  built-in check that a service hasn't accidentally grown a dependency on
  code outside itself.
- **Missing transitive dependency for file uploads.** FastAPI's
  `UploadFile`/`Form` support requires the separate `python-multipart`
  package; omitting it raises a runtime error only once such a route is
  actually hit, not at import time.
- **CORS + credentials is an invalid combination, not just a preference.**
  `allow_origins=["*"]` together with `allow_credentials=True` is rejected
  by the CORS spec itself — browsers will refuse to honor the wildcard when
  credentials are requested, even though the middleware accepts the config
  without complaint. Fix: drop credentials entirely unless genuinely needed,
  since most internal API calls here carry none.
- **Column order from an API response is not guaranteed.** A DataFrame
  built from a JSON API response was assumed to preserve a specific column
  order; explicitly reselecting by name (`df[expected_columns]`) immediately
  after receiving any cross-service data prevents a silent misalignment
  between feature values and feature names.
- **Environment/platform issues, not code bugs.** A Python interpreter
  installed via the Microsoft Store produces a non-standard executable path
  that breaks certain library diagnostics calls. Docker Desktop itself not
  being fully started produces a distinct `npipe` connection error on
  Windows, unrelated to any code or compose-file content.
- **MFA and password auth are for humans, not scheduled scripts.**
  Key-pair authentication is required for unattended/scheduled connections;
  Snowflake additionally requires an explicit network policy (IP allowlist)
  for any non-interactive authentication, independent of MFA.

## Environment setup

- **Snowflake credentials** live only in `data-ingestion-service`'s
  environment (`.env`, gitignored) — no other service receives them, by
  design (least-privilege: only the service that owns the warehouse
  connection can authenticate to it).
- **Inter-service URLs** are environment variables
  (`PREDICTION_SERVICE_URL`, `DATA_INGESTION_SERVICE_URL`, etc.), pointing
  at Docker Compose service names internally (e.g.
  `http://prediction-service:8000`) — never `localhost` between containers.
- **Authentication to Snowflake:** key-pair, not password+MFA.
- **Network policy:** the connecting IP must be allowlisted on the
  Snowflake user for any non-interactive auth. Dynamic/home IPs need this
  updated periodically.
- **CORS:** `monitoring-service` has `CORSMiddleware` enabled
  (`allow_origins=["*"]`, `allow_credentials=False`) so the local UI can
  call it from a different origin.

## What's not built

- **Cloud deployment.** Verified locally via Docker Compose only.
- **External artifact storage (GCS).** `prediction-service` currently
  persists its model artifact to local container disk — required before
  Cloud Run deployment, since local disk doesn't survive a restart or work
  across multiple instances there.
- **Automated alerting/dispatch (n8n).** Severity classification is
  complete and structured; nothing currently pages a human automatically on
  `[CRITICAL]`. The originally designed flow: the monitoring service POSTs
  its weekly report to an n8n webhook, which branches on `Severity` and
  sends a Slack/email alert — n8n would only ever see the lightweight
  severity payload, never touch Snowflake directly.
- **Automated data ingestion.** A future `data-gathering-service` would
  pull from real sources on a schedule and call
  `data-ingestion-service`'s existing `/ingest-batch` endpoint — no changes
  needed to `data-ingestion-service` itself when that's built.
