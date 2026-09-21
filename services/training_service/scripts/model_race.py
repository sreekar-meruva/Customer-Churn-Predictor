import requests
import pandas as pd
import json
from typing import List

def data_acquisition():
    BASE_URL = "http://127.0.0.1:8000"
    URL = BASE_URL+"/churn_predictor/get_data"
    with open(r"services\prediction_service\artifacts\model_metadata.json") as f:
        metadata = json.load(f)
    columns = metadata['feature_columns']
    columns.extend(['Week','Record_id'])
    feature_payload = {
        'table_name':'FEATURE_SNAPSHOT',
        'columns': columns 
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

def model_evaluation(drift_week:int , range: int):
    data = data_acquisition()

if __name__=='__main__':
    data_acquisition()