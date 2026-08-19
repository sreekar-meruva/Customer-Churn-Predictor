# Telecom Churn Prediction & Production Monitoring

An end-to-end churn prediction system built to mirror the responsibilities of an
AI Workflow / ML Operations Analyst role: not just training a model, but
selecting it rigorously, deploying a frozen version, simulating real-world
drift, and building the monitoring/alerting layer that catches degradation
before it silently erodes business value.

## Project motivation

This project rebuilds an earlier churn-prediction exercise (originally a bare
ANN with no evaluation) into a complete, production-minded pipeline: model
selection with proper validation discipline, a frozen deployment artifact, a
simulated production timeline with injected data drift, and an automated
monitoring/alerting system that distinguishes early warning signals (feature
drift) from confirmed impact (performance degradation).

## Pipeline overview

1. **Model selection** (`src/train_evaluate_select.py`)
   Compares Logistic Regression, Random Forest, and XGBoost via stratified
   5-fold cross-validation. Selects scalers based on empirical outlier
   analysis (not default assumption), tunes the classification threshold per
   model by maximizing F2 score (recall weighted above precision, reflecting
   the asymmetric cost of missing a churner), and evaluates calibration via
   Brier score and reliability curves in addition to standard classification
   metrics.

2. **Final training** (`src/train_final.py`)
   Splits data into a training pool and a production pool (stratified, class
   ratio preserved in both). Trains and freezes the selected model
   (Random Forest) on the training pool only, and persists the model,
   optimal threshold, and expected feature schema as versioned artifacts.

3. **Deployment simulation** (`src/simulate_deployment.py`)
   Assigns synthetic weekly timestamps to the production pool, simulating a
   26-week deployment window. Injects a controlled, isolated data drift into
   a single feature starting at a known week, with an automated
   shift-invariance check confirming the injection only moves the
   distribution's location, not its shape.

4. **Drift/performance validation** (`src/validate_drift_detection.py`)
   Runs isolated drift experiments across the model's top-importance
   features, confirming the monitoring logic correctly flags the drifted
   feature (sensitivity) while staying quiet on unaffected features
   (specificity), and quantifies the resulting performance impact
   (F2, precision, recall, Brier loss) pre- vs. post-drift.

5. **Production monitoring** (`src/score_and_monitor.py`)
   The real monitoring entry point: scores the current week's batch against
   the frozen model, computes feature-level drift scores against the
   training-time baseline, and — when ground truth is available — computes
   performance metrics against a statistically-derived baseline (mean +
   2 standard deviations of clean-week Brier scores). Classifies each week
   into a severity tier (OK / WATCH / ALERT / CRITICAL) and writes a
   structured JSON report designed for downstream automation.

## Key findings

- Random Forest outperformed Logistic Regression and XGBoost on F2 score,
  precision, recall, and calibration (Brier loss) simultaneously.
- Feature importance does not reliably predict drift sensitivity: drifting
  the model's top-importance feature did not produce the largest performance
  degradation among the three features tested — different evaluation metrics
  (threshold-based vs. probability-based) disagreed on which feature caused
  the most damage, underscoring the need to track both types of metric.
- A single drifted feature was detectable via distribution monitoring
  (z-score-style comparison against training baseline) before any
  degradation in classification metrics was confirmable — validating a
  two-tier monitoring design where drift scores serve as an early warning
  and performance metrics serve as confirmation once ground truth arrives.

## Repository structure

```
data/
  raw/            source dataset, never modified
  processed/      training/production splits, prepared production stream
src/              all pipeline code
artifacts/        frozen model + metadata (threshold, feature schema, Brier baseline)
reports/          generated weekly monitoring output
```

## Tech stack

Python, pandas, scikit-learn, Linear Regression, Random Forest, XGBoost, Snowflake (planned), n8n (planned) for
workflow automation and alerting.

## Status

Model selection, deployment simulation, drift injection/validation, and
production monitoring logic are complete and tested. Next: Snowflake
integration for prediction/actuals reconciliation, and an n8n workflow for
automated Slack/email alerting on the monitoring script's severity output.
=======
