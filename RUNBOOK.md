# Runbook: Churn Monitoring Pipeline

Operational reference for running, interpreting, and troubleshooting this
project. Written for whoever picks this up next — including future me.

## Execution order

Scripts have hard dependencies on each other's outputs. Run in this order,
always from the project root:

1. `python -m src.train_evaluate_select` — one-time model comparison. Not a
   dependency for anything downstream; informs which model gets frozen.
2. `python -m src.train_final` — trains and freezes the final model, writes
   `artifacts/RandomForest.joblib` and `artifacts/model_metadata.json`, and
   writes `data/processed/training_pool.csv` / `production_pool.csv`.
3. `python -m src.simulate_deployment` — reads `production_pool.csv`, writes
   `data/processed/Production_prepared_stream.csv`.
4. `python -m scripts.setup_snowflake` — one-time (or rare) schema
   provisioning. Requires Snowflake credentials to already be configured
   (see Environment setup below).
5. `python -m scripts.backfill_history` — one-time historical replay.
   Requires steps 1-4 already complete. Safe to re-run: skips weeks already
   present in `PERFORMANCE_LOG`.
6. `python -m src.score_and_monitor` — the ongoing, real monitoring entry
   point. Processes the current (latest) week only. This is what a real
   scheduled job would run repeatedly.

## Severity levels

Produced by `alert_log()` in `src/validate_drift_detection.py`. Two signals
feed the classification: **drift score** (feature distribution vs. training
baseline — always available) and **performance metrics** (F2/precision/
recall/Brier — only available once `Churn` is known for that week's batch).

| Severity | Meaning |
|---|---|
| `OK` | Max feature drift score \|z\| ≤ 0.5. No action needed. |
| `[WARNING]` | Max drift score in (0.5, 1.0]. Worth watching, not urgent. |
| `[ALERT]` | Max drift score > 1.0, but performance impact not yet confirmed (ground truth pending, or confirmed-but-not-degraded). |
| `[CRITICAL]` | Max drift score > 1.0 **and** current Brier loss exceeds `brier_baseline_mean + 1.5*brier_baseline_std`. Both signals agree something is wrong. |

Both thresholds (`1.0` / `0.5` for drift, `1.5*std` for Brier) were derived
by checking the false-positive rate against the actual weeks 1-14 baseline
data, not chosen arbitrarily — see the drift-score and Brier-threshold
sections of the project history for the derivation.

**Known caveat:** weeks 1-14 partly define the baseline they are later
compared against (their own Brier scores contributed to computing
`brier_baseline_mean`). Expect these weeks to trend toward `OK`/`WATCH` by
construction — this isn't the monitoring "working correctly" in the same
sense as a genuinely out-of-sample week being correctly flagged.

## Snowflake schema quick reference

- **`PREDICTIONS`** — one row per (customer, scoring event). `record_id` +
  `week` + `probability`/`prediction`. Written every time a batch is scored,
  regardless of whether ground truth is known yet.
- **`ACTUALS`** — one row per customer, once their outcome resolves.
  `record_id` is the sole primary key (each customer's true churn outcome
  never repeats in this dataset — no periodic re-scoring is modeled).
  Deliberately holds no feature data — join to `PREDICTIONS` for that.
- **`DRIFT_LOG`** — one row per (feature, week). Feature distribution vs.
  training baseline.
- **`PERFORMANCE_LOG`** — one or more rows per week (append-only; a new row
  each time metrics are recomputed, e.g. as coverage improves).
  `computed_at` distinguishes versions; query with `QUALIFY ROW_NUMBER() ...`
  to get the latest estimate per week.

## Known failure modes encountered during development

Kept at the pattern level — what broke, why, and the general lesson, not a
line-by-line diff.

- **Silent leakage from shared mutable state.** An early version of the
  drift-experiment loop reused and saved over the same DataFrame/file across
  what were supposed to be three isolated single-feature experiments,
  causing drift to accumulate across features instead of staying isolated.
  Caught by explicitly checking non-target features' statistics after each
  experiment, not just the targeted one. General lesson: verify a function
  doesn't affect things outside its stated scope, not just that it produces
  the expected output for its main target.
- **Comparisons that always evaluate the same way.** A gap-detection
  function computed differences in the wrong direction for descending-sorted
  data, making every comparison silently non-positive and the check
  permanently unable to fire. Caught by deliberately constructing a case
  where it *should* fire and confirming it did — a check that's never been
  proven to catch a true positive can't be trusted to catch anything.
- **Silent type coercion across library boundaries.** NumPy scalar types
  (`int64`, `float64`), pandas `Index` objects, and `datetime.date` objects
  all fail `json.dump()` silently different ways depending on where they
  entered the pipeline. General lesson: explicitly cast to native Python
  types (`int()`, `float()`, `list()`, `str()`) at the boundary where data
  leaves pandas/NumPy and enters JSON serialization, rather than
  discovering the failure downstream.
- **Environment/platform issues, not code bugs.** A Python interpreter
  installed via the Microsoft Store produces a non-standard executable path
  that breaks certain library diagnostics calls (`platform.libc_ver()`).
  Distinguishing "this is my code" from "this is my environment" mattered
  for not wasting time re-reading working logic.
- **MFA and password auth are for humans, not scheduled scripts.**
  Key-pair authentication is required for unattended/scheduled connections;
  Snowflake additionally requires an explicit network policy (IP allowlist)
  for any non-interactive authentication method, independent of MFA.

## Environment setup

- Snowflake credentials via environment variables (`.env`, gitignored) —
  see `src/utils/snowflake_utils.py` for the required variable names.
- Authentication: key-pair (not password+MFA — see failure modes above).
- Network policy: the connecting IP must be allowlisted on the Snowflake
  user. Home/dynamic IPs will need this updated periodically — see
  `sql/` or the Snowflake user's `NETWORK_POLICY` setting.

## What's not built: automated alerting

`alert_log()` produces a severity string and the surrounding metrics as a
structured dict — this is the complete "decision" layer. What's missing is
the "dispatch" layer: a scheduled trigger, a branch on severity, and a
Slack/email notification. The intended design (not implemented): the Python
monitoring script POSTs its weekly report to an n8n webhook; n8n branches on
the `Severity` field via a Switch node and formats/sends the alert. No
Snowflake access from n8n was planned — Python owns all warehouse writes;
n8n would only ever see the lightweight severity payload.
