from fastapi import FastAPI, HTTPException, status
from services.data_ingestion_service.utils.snowflake_writer import insert_dataframe
from services.data_ingestion_service.utils.snowflake_reader import get_weeks_severity, get_max_db_week
from typing import List, Dict, Any, Optional
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

@app.get("/churn_predictor/get_severity")
def checkSeverity(model_version: str, week: Optional[int]=None, range: Optional[int]=4):
    try:
        if week is None:
            week = get_max_db_week(model_version).get('Week')

        return get_weeks_severity(model_version, week, range)
        
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unable to fetch severity results due to {ex}")