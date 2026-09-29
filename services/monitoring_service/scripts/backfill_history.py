import os
import requests
import pandas as pd
import json
import joblib
from utils.write_logs import write_performance_log, write_drift_log, write_actuals, write_prediction_log
from scripts.score_and_monitor import get_predictions,get_data
from scripts.validate_drift_detection import get_performance_metrics, alert_log, get_drift_scores
import datetime


def get_unique_weeks(table_name:str):
    DATA_INGESTION_URL = os.environ.get("DATA_INGESTION_SERVICE_URL","http://127.0.0.1:8002")
    URL = DATA_INGESTION_URL+"/churn_predictor/get_data"
    payload = {
        "table_name": table_name,
        "columns": ['Week']
    }
    response = requests.post(url = URL, json=payload)
    records = response.json()['records']
    df = pd.DataFrame(data=records, columns=['Week'])
    return df['Week'].unique()

def backfill_logs(metadata):
    try:
        db_weeks = get_unique_weeks(table_name="PERFORMANCE_LOG")
        df = get_data()
        df_weeks = df['Week'].unique()
        features = metadata['feature_columns']
        cont_features = [feature for feature in features if df[feature].nunique()>2]
        for week in df_weeks:
            if week in db_weeks:
                continue
            df_data = df.loc[(df['Week']==week)].reset_index(drop=True)
            write_actuals(df_data)

            drift_scores = get_drift_scores(baseline_stats=metadata['baseline_stats'],prod_stream=df_data, features=cont_features)
            write_drift_log(metadata['baseline_stats'],features=cont_features,drift_scores=drift_scores['drift_scores'],weekly_mean=drift_scores['weekly_means'],week=week)

            pred_df = get_predictions(df_data)
            write_prediction_log(df=pred_df, week=week, date=df_data['Score_date'])
            initial_count = len(pred_df)
            df_data = df_data.dropna(subset='Churn')
            current_count = len(df_data)
            coverage = (current_count/initial_count)*100
            pred_churn_df = pred_df.loc[(pred_df['record_id'].isin(df_data['Record_id']))]
            perf_metrics = get_performance_metrics(pred_churn_df, df_data['Churn']) if coverage>0 else None

            cont_features = [feature for feature in features if df[feature].nunique()>2]
            alert_status = alert_log(drift_scores=drift_scores['drift_scores'],baseline_stats=metadata['brier_baseline_stats'],performance=perf_metrics)

            report = {
                'Week': int(week),
                'Date scored': str(datetime.date.today()),
                'Severity': alert_status,
                'Performance': perf_metrics,
                'Performance scored date': str(datetime.date.today()),
                'Week_performance_coverage': coverage,
                'Week_total_count': initial_count,
                'Week_not_null_count': current_count
            }

            write_performance_log(report, metadata)

    except Exception as e:
        raise Exception(f"Unable to backfill to table PERFORMANCE_LOG due to {e}")

if __name__=="__main__":
    PREDICTION_URL = os.environ.get("PREDICTION_SERVICE_URL")
    URL = PREDICTION_URL+"/churn_predictor/metadata"
    response = requests.get(URL)
    metadata = response.json()
    
    backfill_logs(metadata)