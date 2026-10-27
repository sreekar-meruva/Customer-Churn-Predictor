import os
import requests
from fastapi import FastAPI, UploadFile,File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from typing import Union
from scripts.score_and_monitor import start_monitor

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_methods=['*'],
    allow_origins=['*'],
    allow_headers=['*']
)

PREDICTION_URL = os.environ.get('PREDICTION_SERVICE_URL','http://127.0.0.1:8001')
INGESTION_URL = os.environ.get('DATA_INGESTION_SERVICE_URL','http://127.0.0.1:8002')

def get_metadata():
    pred_url = PREDICTION_URL+"/churn_predictor/metadata"
    response = requests.get(url=pred_url)
    return response.json()

def featureSnapshotUpload(dataframe: pd.DataFrame):
    df = dataframe.copy()
    df = df.drop(columns=['Churn'])
    inges_url = INGESTION_URL+"/churn_predictor/upload_data"
    data_dict = df.to_dict(orient="records")
    payload = {
        'data': data_dict,
        'table': 'FEATURE_SNAPSHOT'
    }
    response = requests.post(url=inges_url, json=payload)
    response.raise_for_status()
    return response

def actualsUpload(dataframe: pd.DataFrame):
    df = dataframe[['Record_id','Churn','Score_date','Week']].copy()
    df = df.rename(columns={'Record_id':'record_id','Churn':'churn','Score_date':'known_date','Week':'week'})
    df = df.dropna(subset=["churn"])
    if df.empty:
        return None
    data_dict = df.to_dict(orient='records')
    inges_url = INGESTION_URL+'/churn_predictor/upload_data'
    payload={
        'data': data_dict,
        'table': 'ACTUALS'
    }
    response = requests.post(url=inges_url, json=payload)
    response.raise_for_status()
    return response

@app.post("/churn_predictor/monitor")
def trigger_monitoring_service(file: Union[UploadFile,str,None]=File(default=None)):
    if isinstance(file, str):
        file=None
    if file:
        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid file type")
        try:
            new_df = pd.read_csv(file.file)
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unreadable CSV")
        try:
            metadata = get_metadata()
            req_fields = metadata.get("required_fields")
            new_df_cols = new_df.columns
            for field in req_fields:
                if field not in new_df_cols:
                    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Field {field} is missing in the data")
            featureSnapshotUpload(new_df)
            actualsUpload(new_df)
        except requests.RequestException as ex:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Upload failed due to {ex}")

    try:
        return start_monitor()
    except Exception as ex:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unable to start the monitor due to {ex}")
    