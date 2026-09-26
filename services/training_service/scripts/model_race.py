import requests
import pandas as pd
import numpy as np
import math
import json
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import fbeta_score, recall_score, brier_score_loss
from typing import List, Any

BASE_URL = "http://127.0.0.1:8000/churn_predictor"
with open(r"services\prediction_service\artifacts\model_metadata.json") as f:
        metadata = json.load(f)

MODEL_PATH = r"services\prediction_service\artifacts\RandomForest.joblib"

def data_acquisition(features: List[str]):
    URL = BASE_URL+"/get_data"
    features.extend(['Week','Record_id'])
    feature_payload = {
        'table_name':'FEATURE_SNAPSHOT',
        'columns': features 
    }

    response = requests.post(url=URL, json=feature_payload)
    records = response.json()['records']
    feature_df = pd.DataFrame(data = records, columns = columns)
    columns = ['Churn','Week','Record_id']
    actuals_payload = {
        'table_name': "ACTUALS",
        'columns': columns
    }
    response = requests.post(url=URL, json = actuals_payload)
    records = response.json()['records']
    actuals_df = pd.DataFrame(data = records, columns = columns)
    dataset = pd.merge(left=feature_df, right=actuals_df, on=['Record_id','Week'], how='inner')
    return dataset

def get_optimal_threshold(model: Any, data: pd.DataFrame):
    thresholds = np.arange(start=0.1, stop=0.9, step=0.05)
    X_data = data[metadata['feature_columns']]
    y_data = data['Churn']
    optimal_threshold = 0
    max_f2 = 0
    for threshold in thresholds:
        probs = model.predict_proba(X_data)
        predictions = (probs>=threshold).astype(int)
        f2_score = fbeta_score(y_data, predictions, beta=2)
        if(max_f2<f2_score):
            optimal_threshold = threshold
            max_f2 = f2_score
    return optimal_threshold


def get_metrics(model: Any, X_data: pd.DataFrame, y_true: pd.Series, threshold: float):
     probs = model.predict_proba(X_data)
     predicts = (probs>=threshold).astype(int)
     f2 = fbeta_score(y_true, predicts, beta=2)
     recall = recall_score(y_true, predicts)
     brier_loss = brier_score_loss(y_true, probs)
     return{
          'f2_score': f2,
          'recall_score': recall,
          'brier_loss': brier_loss
     }

def trigger_monitor():
    URL = BASE_URL+"/monitor"
    response = requests.post(URL)
    if response.status_code:
        print("Monitor triggered successfully!")
     

def evaluate_and_select(candidate_model: Any, train_data: pd.DataFrame, test_data: pd.DataFrame):
    champion_model = joblib.load(MODEL_PATH)
    champion_threshold = metadata['threshold']
    candidate_threshold = get_optimal_threshold(candidate_model, test_data)
    y_true = test_data['Churn']
    X_data = test_data[metadata['feature_columns']]
    champion_metrics = get_metrics(champion_model, X_data, y_true, champion_threshold)
    candidate_metrics = get_metrics(candidate_model, X_data, y_true, candidate_threshold)

    f2_improvement = (candidate_metrics['f2_score']>champion_metrics['f2_score'])
    recall_check = candidate_metrics['recall_score']>=(champion_metrics['recall_score']-0.02)
    brier_check = candidate_metrics['brier_loss']<=(champion_metrics['brier_loss']+1.1)

    if f2_improvement and recall_check and brier_check:
        joblib.dump(candidate_model, MODEL_PATH)
        train_data.to_csv(r"data\processed\training_pool.csv")
        model = metadata['model']
        model_version = 1 if model=='RandomForestClassifer' else int(model.strip('RandomForestClassifer_v'))
        metadata = {
            'model': "RandomForestClassifer_v"+str(model_version+1),
            'threshold': candidate_threshold,
            'feature_columns': metadata['feature_columns'],
            'model_deployment_week': np.max(test_data['Week'])
        }
        with open(r"services\prediction_service\artifacts\model_metadata.json",'w') as f:
            json.dump(metadata,f)
        trigger_monitor()
    elif f2_improvement and not recall_check:
        print("Review models closely")
    else:
        print("Review models")

def model_train(drift_week:int, range: int):
    features = metadata['feature_columns']
    data = data_acquisition(features)
    last_model_update = metadata['model_deployment_week']
    model_version = metadata['model']
    range = min(range, drift_week-last_model_update)
    URL = BASE_URL+"/get_severity"
    payload = {
         'model_version': model_version,
         'week': drift_week,
         'range': range
    }
    response = requests.get(URL,params = payload)
    records = response.json()
    critical_weeks = [record['Week'] for record in records if record['Severity']=='[CRITICAL]']
    drift_start = drift_week-len(critical_weeks)
    margin_week = drift_start+math.ceil(0.75*len(critical_weeks))
    is_train = data['Week']<margin_week
    train_data = data.loc[np.where(is_train)]
    test_data = data.loc[np.where(~is_train)]
    weights = np.where(np.isin(train_data['Week'],critical_weeks),3,1)
    X_train = train_data[features]
    y_train = train_data['Churn']
    candidate_model = RandomForestClassifier()
    candidate_model.fit(X_train, y_train, sample_weight=weights)
    evaluate_and_select(candidate_model, train_data, test_data)

if __name__=='__main__':
    data_acquisition()