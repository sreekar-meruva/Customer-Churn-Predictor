# Telecom Churn Prediction & Production Monitoring

An end-to-end churn prediction system built to mirror the responsibilities of an
AI Workflow / ML Operations Analyst role: rigorous model selection, a frozen
deployment artifact, a simulated production timeline with injected data drift,
and a Snowflake-backed monitoring/reconciliation layer that distinguishes
early warning signals (feature drift) from confirmed impact (performance
degradation).

## Project motivation

This project rebuilds an earlier churn-prediction exercise (originally a bare
ANN with no evaluation) into a complete, production-minded pipeline: model
selection with proper validation discipline, a frozen deployment artifact, a
simulated production timeline with injected data drift, a Snowflake data
warehouse for predictions/actuals/monitoring history, and reconciliation
queries that connect model behavior back to real outcomes.

## Pipeline overview

1. **Model selection** (`src/train_evaluate_select.py`)
   Compares Logistic Regression, Random Forest, and XGBoost via stratified
   5-fold cross-validation. Scaler choice is decided from empirical outlier
   analysis rather than default assumption. Classification threshold is
   tuned per model by maximizing F2 score (recall weighted above precision,
   reflecting the asymmetric cost of missing a churner). Evaluation includes
   calibration (Brier score, reliability curves), not just classification
   metrics. **Winner: Random Forest** — best F2 (~0.75 at threshold 0.25),
   best precision/recall together, lowest Brier loss (~0.054).

2. **Final training** (`src/train_final.py`)
   Stratified 60/40 split into a training pool and a production pool (class
   ratio preserved in both). Trains and freezes Random Forest on the
   training pool only. Persists the model, threshold, and feature schema as
   versioned artifacts (`artifacts/`). Each row carries a unique `record_id`
   (UUID), assigned before the split to guarantee global uniqueness.

3. **Deployment simulation** (`src/simulate_deployment.py`)
   Assigns synthetic per-row weekly timestamps to the production pool,
   simulating a 26-week deployment window. Includes a validated,
   shift-invariant drift injection mechanism (used in controlled experiments,
   not applied to the live monitoring stream).

4. **Drift/performance validation** (`src/validate_drift_detection.py`)
   Runs isolated, single-feature drift experiments across the model's
   top-importance features, confirming detection logic correctly flags a
   drifted feature (sensitivity) while staying quiet on unaffected features
   (specificity). Finding: feature importance did not reliably predict
   drift-impact severity — different metrics (F2 vs. Brier) disagreed on
   which feature caused the most damage.

5. **Production monitoring** (`src/score_and_monitor.py`)
   Scores the current week's batch against the frozen model, computes
   feature-level drift scores against the training-time baseline, and —
   when ground truth is available — computes coverage-aware performance
   metrics against a statistically-derived baseline (mean + N×std of
   clean-week Brier scores). Classifies each week into a severity tier
   (OK / WATCH / ALERT / CRITICAL) and writes results to Snowflake.

6. **Historical backfill** (`scripts/backfill_history.py`)
   One-time script that replays the full 26-week simulated history through
   the monitoring logic, populating Snowflake with a complete historical
   record rather than only the most recent week.

7. **Snowflake data warehouse** (`sql/ddl/`, `sql/queries/`)
   Four tables — `PREDICTIONS`, `ACTUALS`, `DRIFT_LOG`, `PERFORMANCE_LOG` —
   designed around append-only, time-lag-aware grain (a prediction and its
   eventual actual outcome are separate events, joined by `record_id`, not
   assumed to arrive together). Reconciliation queries join predictions
   against resolved actuals to validate model behavior directly from the
   warehouse.

## Key findings

- Random Forest outperformed Logistic Regression and XGBoost on F2 score,
  precision, recall, and calibration (Brier loss) simultaneously.
- Feature importance does not reliably predict drift sensitivity: drifting
  the model's top-importance feature did not produce the largest performance
  degradation among the three features tested.
- A single drifted feature was detectable via distribution monitoring before
  any degradation in classification metrics was confirmable — validating a
  two-tier monitoring design where drift scores serve as an early warning
  and performance metrics serve as confirmation once ground truth arrives.
- Reconciling live predictions against actuals in Snowflake showed a 90.1%
  match rate overall, consistent with the model's known precision/recall on
  the minority (churn) class. Isolating "confidently wrong" predictions
  (probability < 0.15 but actually churned) found this error type spread
  across weeks 3-25, not concentrated near any particular point — correctly
  ruling out drift as the cause (the live production stream was never
  drifted) and instead pointing to an inherent, roughly-constant rate of
  confident misclassification, consistent with the mild overconfidence
  pattern already observed in the model's calibration curve.

## Repository structure

```
data/
  raw/            source dataset, never modified
  processed/      training/production splits, prepared production stream
src/
  utils/          shared helpers (Snowflake connection, generic insert)
artifacts/        frozen model + metadata (threshold, feature schema, baselines)
scripts/          one-off operational scripts (schema setup, backfill)
sql/
  ddl/            table definitions
  queries/        reconciliation and investigation queries
reports/          generated weekly monitoring output
RUNBOOK.md        operational reference: severity levels, known failure
                  modes, environment setup
```

## Tech stack

Python, pandas, scikit-learn, XGBoost, Snowflake (key-pair authenticated),
snowflake-connector-python.

## Status and known limitations

Model selection, deployment simulation, drift injection/validation, Snowflake
schema, and production monitoring/reconciliation are complete and verified
against real data.

**Not implemented:** an automated alerting workflow (n8n) that consumes the
weekly severity classification and dispatches Slack/email notifications. The
classification logic itself (`alert_log`) is complete and produces a
structured severity output ready for such a workflow to consume — the
orchestration/dispatch layer was scoped out to prioritize finishing the
Python/Snowflake pipeline end-to-end. See `RUNBOOK.md` for what this would
require.

**Other known gaps**, documented rather than silently left out: no persistent
`customer_id` (the source dataset has no real longitudinal customer identity,
so `record_id` identifies a scoring instance, not a person); `predictions`
has no `model_version` column (acceptable for a single deployed model, would
need revisiting before supporting model version comparisons).
