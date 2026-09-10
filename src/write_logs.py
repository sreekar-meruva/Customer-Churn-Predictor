import pandas as pd
from api.utils.snowflake_writer import insert_dataframe
import datetime
import uuid
import requests

BASE_URL = 'http://127.0.0.1:8000'

def upload_to_snowflake(dataframe, table):
    URL = BASE_URL+"/datainsertion/snowflake"
    data_dict = dataframe.to_dict(orient='records')
    payload = {
        'data': data_dict,
        'table': table
    }
    response = requests.post(url = URL, json=payload)
    if response.status_code==200:
        return response.text
    return "[ERROR] Encountered error while uploading"

def write_performance_log(stats,metadata):
    table_name = "PERFORMANCE_LOG"
    report={
        "week": stats['Week'],
        'model_version': metadata['model'],
        'batch_count': stats['Week_total_count'],
        'f2_score': stats['Performance']['F2 Score'] if stats['Performance'] != None else None,
        'precision_score': stats['Performance']['Precision'] if stats['Performance']!=None else None,
        'recall_score': stats['Performance']['Recall'] if stats['Performance']!=None else None,
        'brier_loss': stats['Performance']['Brier loss score'] if stats['Performance']!=None else None,
        'brier_threshold': metadata['brier_baseline_stats']['mean']+(1.5*metadata['brier_baseline_stats']['std']),
        'severity': stats['Severity'],
        'computed_at': stats['Date scored'],
        'coverage': stats['Week_performance_coverage'],
        'not_na_count': stats['Week_not_null_count']
    }
    performance_df = pd.DataFrame([report])
    response = upload_to_snowflake(performance_df, table_name)
    print(response)

def write_prediction_log(df, week, date = None):
    table_name = 'PREDICTIONS'
    if date is None:
        final_date = str(datetime.datetime.today())
    elif isinstance(date,pd.Series):
        final_dates = date.fillna(pd.Timestamp.today().date())
        final_date = [str(final_date) for final_date in final_dates]
    else:
        final_date = str(date)
    
    df = df.copy()
    df['prediction_id'] = [str(uuid.uuid4()) for _ in range(len(df))]
    df['week'] = week
    df['score_date'] = final_date
    df['score_at'] = str(datetime.datetime.now())
    df = df.rename(columns={'probabilities':'probability','predictions':'prediction'})
    response = upload_to_snowflake(df, table_name)
    print(response)

def write_actuals(prod_df):
    table_name = "ACTUALS"
    actuals_df = prod_df[['Record_id','Churn','Score_date','Week']]
    actuals_df = actuals_df.dropna(subset='Churn')
    actuals_df = actuals_df.rename(columns={'Record_id':'record_id','Churn':'churn','Score_date':'known_date','Week':'week'})
    response = upload_to_snowflake(actuals_df, table_name)
    print(response)

def write_drift_log(baseline_stats, features, drift_scores, weekly_mean, week):
    table_name = "DRIFT_LOG"
    drift_df = pd.concat([weekly_mean,drift_scores]).reset_index(drop=True)
    drift_df = drift_df.T.reset_index(drop=True)
    drift_df.columns = ['week_mean','drift_score']
    series_mean = pd.Series(baseline_stats['mean']).reset_index(drop=True)
    series_std = pd.Series(baseline_stats['std']).reset_index(drop=True)
    series_features = pd.Series(features)
    drift_df['week'] = week
    drift_df['feature'] = series_features
    drift_df['base_mean'] = series_mean
    drift_df['base_std'] = series_std
    drift_df['computed_at'] = str(pd.Timestamp.now())    

    response = upload_to_snowflake(drift_df, table_name)
    print(response)