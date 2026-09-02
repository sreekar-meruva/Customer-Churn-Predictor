import json
import joblib
import pandas as pd
import numpy as np
import uuid
import datetime
from src.validate_drift_detection import get_drift_scores, get_performance_metrics, alert_log, get_model_predictions
from src.utils.snowflake_writer import insert_dataframe
from sklearn.metrics import brier_score_loss

def  monitor_input_output(model, prod_stream, metadata):
    threshold = metadata['threshold']
    features = metadata['feature_columns']
    brier_baseline_stats = metadata['brier_baseline_stats']
    week = prod_stream['Week'].max()
    continuous_features = [col for col in features if prod_stream[col].nunique()>2]
    baseline_stats = metadata['baseline_stats']

    get_drift = get_drift_scores(baseline_stats, prod_stream[(prod_stream['Week']==week)], continuous_features)

    batch = prod_stream.loc[(prod_stream['Week']==week)]
    pred_df = get_model_predictions(model, threshold, batch, features)

    write_prediction_log(pred_df,week)

    initial_batch_count = len(batch)
    batch = batch.dropna(subset='Churn')
    current_batch_count = len(batch)
    coverage_percent = (current_batch_count/initial_batch_count)*100
    pred_churn_df = pred_df.loc[(pred_df['record_id'].isin(batch['Record_id']))]
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

    return report

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
    performance_report_df = pd.DataFrame([report])
    print(insert_dataframe(performance_report_df,table_name))

def write_prediction_log(df, week, date = None):
    table_name = 'PREDICTIONS'
    if date is None:
        final_date = datetime.datetime.today()
    elif isinstance(date,pd.Series):
        final_date = date.fillna(pd.Timestamp.today().date())
    else:
        final_date = date
    
    df = df.copy()
    df['prediction_id'] = [str(uuid.uuid4()) for _ in range(len(df))]
    df['week'] = week
    df['score_date'] = final_date
    df['score_at'] = str(datetime.datetime.now())
    df = df.rename(columns={'probabilities':'probability','predictions':'prediction'})
    print(insert_dataframe(df, table_name))

def write_actuals(prod_df):
    table_name = "ACTUALS"
    actuals_df = prod_df[['Record_id','Churn','Score_date','Week']]
    actuals_df = actuals_df.dropna(subset='Churn')
    actuals_df = actuals_df.rename(columns={'Record_id':'record_id','Churn':'churn','Score_date':'known_date','Week':'week'})
    print(insert_dataframe(actuals_df,table_name))

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
    
    print(insert_dataframe(drift_df,table_name))

def main():
    model = joblib.load(r"artifacts\RandomForest.joblib")
    train_pool = pd.read_csv(r"data\processed\training_pool.csv")
    with open(r"artifacts\model_metadata.json") as f:
        metadata=json.load(f)

    prod_stream = pd.read_csv(r"data\processed\Production_prepared_stream.csv")

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
    main()
