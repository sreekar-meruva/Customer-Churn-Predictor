from fastapi import FastAPI, HTTPException, Request, status
from api.utils.snowflake_writer import insert_dataframe
import pandas as pd


app = FastAPI()

@app.post("/datainsertion/snowflake")
def insertToSnowflake(data: dict):
    dataframe = data["dataframe"]
    table_name = data['table']
    try:
        insert_dataframe(dataframe, table_name)
        return {
            'status': status.HTTP_200_OK,
            'detail': f"Data uploaded to {table_name} successfully!"
        }
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_417_EXPECTATION_FAILED, detail=f"Unable to upload data to table due to {ex}")
    