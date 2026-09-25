import json
import joblib
import pandas as pd
import numpy as np
import requests
from typing import Optional
import datetime
from services.monitoring_service.scripts.validate_drift_detection import get_drift_scores, get_performance_metrics, alert_log
from src.write_logs import write_performance_log, write_prediction_log, write_actuals, write_drift_log
from sklearn.metrics import brier_score_loss

BASE_URL = "http://127.0.0.1:8000/churn_predictor"

def  monitor_input_output(model, prod_stream, metadata):
    features = metadata['feature_columns']
    brier_baseline_stats = metadata['brier_baseline_stats']
    week = prod_stream['Week'].max()
    continuous_features = [col for col in features if prod_stream[col].nunique()>2]
    baseline_stats = metadata['baseline_stats']

    get_drift = get_drift_scores(baseline_stats, prod_stream[(prod_stream['Week']==week)], continuous_features)

    batch = prod_stream.loc[(prod_stream['Week']==week)]
    pred_df = get_predictions(batch, metadata)

    write_prediction_log(pred_df,week)

    initial_batch_count = len(batch)
    batch = batch.dropna(subset='Churn')
    current_batch_count = len(batch)
    coverage_percent = (current_batch_count/initial_batch_count)*100
    pred_churn_df = pred_df.loc[(pred_df['Record_id'].isin(batch['Record_id']))]
    performance_metrics = get_performance_metrics(pred_churn_df, batch['Churn']) if coverage_percent>0 else None

    write_drift_log(baseline_stats, continuous_features, get_drift['drift_scores'], get_drift['weekly_means'], week)

    alert_status = alert_log(get_drift['drift_scores'], brier_baseline_stats, performance_metrics)

    report = {
        'Week': int(week),
        'Date scored': str(datetime.date.today()),
        'Severity': alert_status,
        'Performance': performance_metrics,
        'Performance scored date': str(datetime.date.today()),
        'Week_performance_coverage': coverage_percent,
        'Week_total_count': initial_batch_count,
        'Week_not_null_count': current_batch_count
    }

    write_performance_log(report,metadata)

    if "[CRITICAL]" in alert_status:
        if check_retrain_requirement(metadata['model']):
            trigger_model_retrain(week)

    write_actuals(prod_stream[(prod_stream['Week']==report['Week'])])
    return report

def trigger_model_retrain(drift_week: int, severity_range: Optional[int]=18):
    URL = BASE_URL+'/retrain_model'
    payload = {
        'drift_week': drift_week,
        'range': severity_range
    }
    response = requests.post(URL, json=payload)
    detail = response.json()['detail']
    print(detail)

def check_retrain_requirement(model_version, week: Optional[int]=None, range: Optional[int]=6):
    URL = BASE_URL+"/get_severity"
    payload = {
        'model_version': model_version,
        'week': week,
        'range': range
    }
    response = requests.get(URL, params=payload)
    response.raise_for_status()
    response = response.json()
    if len(response) < range:
        return False
    return all('CRITICAL' in record['Severity'] for record in response)

def compute_baseline_stats(train_pool, features):
    baseline_stats = train_pool[features].agg(['mean','std'])
    mean = baseline_stats.loc['mean']
    std = baseline_stats.loc['std']
    return {
        'mean': mean.to_dict(),
        'std': std.to_dict()
    }

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

def get_predictions(batch: pd.DataFrame, metadata: json):
    URL = BASE_URL+"/predict"
    features = ['Record_id']+metadata['feature_columns']
    batch = batch[features]
    batch_dict = batch.to_dict(orient="records")
    payload = {
        'batch': batch_dict
    }
    response = requests.post(url = URL, json=payload)
    response_df = pd.DataFrame(response.json())
    return(response_df)


def start_monitor(prod_stream: pd.DataFrame):
    model = joblib.load(r"artifacts\RandomForest.joblib")
    train_pool = pd.read_csv(r"data\processed\training_pool.csv")
    with open(r"artifacts\model_metadata.json") as f:
        metadata=json.load(f)

    prod_stream = pd.read_csv(r"data\processed\Production_prepared_stream.csv") if prod_stream is None else prod_stream

    if "baseline_stats" not in metadata.keys():
        continuous_features = [feature for feature in metadata['feature_columns'] if prod_stream[feature].nunique()>2]
        metadata["baseline_stats"] = compute_baseline_stats(train_pool, continuous_features)

    if "brier_baseline_stats" not in metadata.keys():
        metadata['brier_baseline_stats'] = compute_baseline_brier(model, prod_stream, metadata['feature_columns'])

    report = monitor_input_output(model, prod_stream, metadata)
    with open("Weekly report.json",'w') as f:
        json.dump(report, f)
    with open(r"artifacts\model_metadata.json",'w') as f:
        json.dump(metadata,f)

    write_actuals(prod_stream[(prod_stream['Week']==report['Week'])])
    return report

if __name__ == "__main__":
    start_monitor()
