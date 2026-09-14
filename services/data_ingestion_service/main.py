from fastapi import FastAPI, HTTPException, status
from services.data_ingestion_service.utils.snowflake_writer import insert_dataframe
from services.data_ingestion_service.utils.snowflake_reader import get_weeks_severity
from typing import List, Dict, Any
import pandas as pd
from pydantic import BaseModel

app = FastAPI()

class InsertionRequest(BaseModel):
    data: List[Dict[str,Any]]
    table: str

class SeverityValidationRequest(BaseModel):
    model_version: str
    week: int
    range: int

@app.post("/churn_predictor/upload_data")
def insertToSnowflake(payload: InsertionRequest):
    table_name = payload.table
    try:
        dataframe = pd.DataFrame(payload.data)
        insert_dataframe(dataframe, table_name)
        return {
            'Detail': f"Data uploaded to {table_name} successfully!"
        }
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_417_EXPECTATION_FAILED, detail=f"Unable to upload data to table due to {ex}")

@app.post("/churn_predictor/check_severity")
def checkSeverity(payload: SeverityValidationRequest):
    try:
        records = get_weeks_severity(payload.model_version, payload.week, payload.range)
        check=True
        for record in records:
            if not record['Severity'].contains("[CRITICAL]"):
                check=False
                break
        return {
            "Retrain_alert": check 
        }
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unable to validate severity due to {ex}")