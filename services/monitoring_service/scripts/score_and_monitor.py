import json
import os
import joblib
import pandas as pd
import numpy as np
import requests
from typing import Optional
import datetime
from services.monitoring_service.scripts.validate_drift_detection import get_drift_scores, get_performance_metrics, alert_log
from services.monitoring_service.utils.write_logs import write_performance_log, write_prediction_log, write_actuals, write_drift_log
from sklearn.metrics import brier_score_loss

def get_metadata():
    PREDICTION_URL = os.environ.get("PREDICTION_SERVICE_URL","http://127.0.0.1:8001")
    URL = PREDICTION_URL+"/churn_predictor/metadata"
    response = requests.get(URL)
    metadata = response.json()
    return metadata

PREDICTION_URL = os.environ.get("PREDICTION_SERVICE_URL","http://127.0.0.1:8001")
DATA_INGESTION_URL = os.environ.get("DATA_INGESTION_SERVICE_URL","http://127.0.0.1:8002")
metadata = get_metadata()

def  monitor_input_output(prod_stream, metadata):
    features = metadata['feature_columns']
    brier_baseline_stats = metadata['brier_baseline_stats']
    week = prod_stream['Week'].max()
    continuous_features = [col for col in features if prod_stream[col].nunique()>2]
    baseline_stats = metadata['baseline_stats']

    get_drift = get_drift_scores(baseline_stats, prod_stream[(prod_stream['Week']==week)], continuous_features)

    batch = prod_stream.loc[(prod_stream['Week']==week)]
    pred_df = get_predictions(batch)

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
    TRAINING_URL = os.environ.get("TRAINING_SERVICE_URL","http://127.0.0.1:8003")
    URL = TRAINING_URL+'/churn_predictor/retrain_model'
    payload = {
        'drift_week': drift_week,
        'range': severity_range
    }
    response = requests.post(URL, json=payload)
    detail = response.json()['detail']
    print(detail)

def check_retrain_requirement(model_version, week: Optional[int]=None, range: Optional[int]=6):
    DATA_INGESTION_URL = os.environ.get("DATA_INGESTION_SERVICE_URL","http://127.0.0.1:8002")
    URL = DATA_INGESTION_URL+"/churn_predictor/get_severity"
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

def get_predictions(batch: pd.DataFrame):
    URL = PREDICTION_URL+"/churn_predictor/predict"
    features = ['Record_id']+metadata['feature_columns']
    batch = batch[features]
    batch_dict = batch.to_dict(orient="records")
    payload = {
        'batch': batch_dict
    }
    response = requests.post(url = URL, json=payload)
    response_df = pd.DataFrame(response.json())
    return(response_df)

def get_data():
    URL = DATA_INGESTION_URL+"/churn_predictor/get_data"
    features = metadata['feature_columns'].extend(["Record_id", "Week"])
    feature_payload = {
        'table_name': "FEATURE_SNAPSHOT",
        'columns': features
    }
    response = requests.post(url = URL, json=feature_payload)
    records = response.json()['records']
    features_df = pd.DataFrame(data=records, columns = features)
    actuals_columns = ['Churn', 'Record_id', 'Week']
    actuals_payload = {
        'table_name': "ACTUALS",
        'columns': actuals_columns
    }
    response = requests.post(url=URL, json=actuals_payload)
    records = response.json()['records']
    actuals_df = pd.DataFrame(data=records,columns=actuals_columns)

    df = pd.merge(left=features_df, right=actuals_df, on=["Record_id","Week"])
    return(df)

def start_monitor():
    prod_stream = get_data()
    report = monitor_input_output(prod_stream, metadata)
    with open(r"services\monitoring_service\reports\Weekly report.json",'w') as f:
        json.dump(report, f)

    write_actuals(prod_stream[(prod_stream['Week']==report['Week'])])
    return report

if __name__ == "__main__":
    start_monitor()
