import json
import joblib
import pandas as pd
import numpy as np
import datetime
from src.validate_drift_detection import get_drift_scores, get_performance_metrics, alert_log
from sklearn.metrics import brier_score_loss

def monitor_input_output(model, train_pool, prod_stream, metadata):
    threshold = metadata['threshold']
    features = metadata['feature_columns']
    brier_baseline_stats = metadata['brier_baseline_stats']
    week = prod_stream['Week'].max()
    continuous_features = [col for col in features if prod_stream[col].nunique()>2]

    baseline_stats = train_pool[continuous_features].agg(['mean','std'])
    drift_scores = get_drift_scores(baseline_stats, prod_stream[(prod_stream['Week']==week)], continuous_features)

    performance_metrics = None

    if 'Churn' in prod_stream.columns:
        batch = prod_stream.loc[(prod_stream['Week']==week)]
        performance_metrics = get_performance_metrics(model, threshold, batch, features)

    alert_status = alert_log(drift_scores, brier_baseline_stats, performance_metrics)

    report = {
        'Week': int(week),
        'Date scored': str(datetime.date.today()),
        'Severity': alert_status,
        'Performance': None,
        'Performance scored date': None
    }

    if performance_metrics:
        report['Performance'] = performance_metrics
        report['Performance scored date'] = str(datetime.date.today())

    return report

def compute_baseline_brier(model, prod_stream,features):
    brier_scores=[]
    for week, batch in prod_stream[(prod_stream['Week']<15)].groupby('Week'):
        probs = model.predict_proba(batch[features])[:,1]
        brier_scores.append(
            brier_score_loss(batch['Churn'], probs)
        )

    return {
        'mean': np.mean(brier_scores),
        'std': np.std(brier_scores)
    }


def main():
    model = joblib.load("RandomForest.joblib")
    train_pool = pd.read_csv("training_pool.csv")
    with open("model_metadata.json") as f:
        metadata=json.load(f)

    prod_stream = pd.read_csv("Test_File.csv")
    if 'brier_baseline_stats' not in metadata.keys():
        brier_baseline_stats = compute_baseline_brier(model, prod_stream, metadata['feature_columns'])
        metadata['brier_baseline_stats'] = brier_baseline_stats
    
    report = monitor_input_output(model, train_pool, prod_stream, metadata)
    with open("Weekly report.json",'w') as f:
        json.dump(report, f)
    with open("model_metadata.json",'w') as f:
        json.dump(metadata,f)

    return report

if __name__ == "__main__":
    main()
