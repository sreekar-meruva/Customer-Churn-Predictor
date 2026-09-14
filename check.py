import requests
import pandas as pd
import json
from fastapi import status
from services.data_ingestion_service.utils.snowflake_reader import get_max_db_week

BASE_URL = "http://127.0.0.1:8000"

def verify_records():
    with open(r"services\prediction_service\artifacts\model_metadata.json") as f:
        metadata = json.load(f)

    URL = BASE_URL+"/churn_predictor/get_severity"
    payload = {
        'model_version': metadata['model']
    }
    response = requests.get(URL, payload)
    print(response.json())

if __name__=="__main__":
    verify_records()