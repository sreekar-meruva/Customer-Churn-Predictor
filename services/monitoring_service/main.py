import os
import requests
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io
import json
from typing import Optional
from scripts.score_and_monitor import start_monitor
from utils.write_logs import write_actuals

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_methods=['*'],
    allow_origins=['*'],
    allow_headers=['*']
)

INGESTION_URL = os.environ.get('DATA_INGESTION_SERVICE_URL','http://127.0.0.1:8002')

@app.post("/churn_predictor/monitor")
async def trigger_monitoring_service(file: Optional[UploadFile] = None):
    if file:
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unable to process the file due to invalid file type")
        content = await file.read()
        data = io.BytesIO(content).getvalue().decode("utf-8")
        contents = data.splitlines()
        cols = contents[0].split(",")
        values = [content.split(",") for content in contents[1:]]
        new_df = pd.DataFrame(data=values, columns=cols)
        URL = INGESTION_URL+"/churn_predictor/get_data"
        payload = {
            'table_name': 'FEATURE_SNAPSHOT',
            'limit':1
        }
        old_df = requests.post(url = URL, json=payload)
        columns = [column for column in old_df.columns]
        columns.append('churn')
        if len(columns)!=len(new_df.columns):
            raise HTTPException(status_code = status.HTTP_422_UNPROCESSABLE_ENTITY, details="Column length mismatch")
        for column in new_df.columns:
            if column.lower() not in columns:
                raise HTTPException(status_code = status.HTTP_422_UNPROCESSABLE_ENTITY, details="Columns in the data file mismatch")
        actuals_df = new_df[(new_df['Churn']!=None)]
        actuals_df = actuals_df[['Record_id','Churn','Score_date','Week']]
        write_actuals(actuals_df)
        feature_df = new_df.drop(['Churn'])
        feature_dict = feature_df.to_dict(orient='records')
        URL = INGESTION_URL+"/churn_predictor/upload_data"
        payload = {
            'data': feature_dict,
            'table': 'FEATURE_SNAPSHOT'
        }
        requests.post(url = URL, json=payload)
    start_monitor()
    