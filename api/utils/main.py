from fastapi import FastAPI, HTTPException, Request, status
from api.utils.snowflake_writer import insert_dataframe
from typing import List, Dict, Any
import pandas as pd
from pydantic import BaseModel

app = FastAPI()

class InsertionRequest(BaseModel):
    data: List[Dict[str,Any]]
    table: str

@app.post("/datainsertion/snowflake")
def insertToSnowflake(payload: InsertionRequest):
    print('Checkpoint1')
    table_name = payload.table
    try:
        dataframe = pd.DataFrame(payload.data)
        insert_dataframe(dataframe, table_name)
        return {
            'status': status.HTTP_200_OK,
            'detail': f"Data uploaded to {table_name} successfully!"
        }
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_417_EXPECTATION_FAILED, detail=f"Unable to upload data to table due to {ex}")
    