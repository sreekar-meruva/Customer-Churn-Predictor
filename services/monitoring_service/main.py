from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io
from services.monitoring_service.scripts.score_and_monitor import start_monitor

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=['*'],
    allow_origins=['*'],
    allow_headers=['*']
)

@app.post("/churn_predictor/monitor")
async def trigger_monitoring_service(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unable to process the file due to invalid file type")
    content = await file.read()
    data = io.BytesIO(content).getvalue().decode("utf-8")
    contents = data.splitlines()
    cols = contents[0].split(",")
    values = [content.split(",") for content in contents[1:]]
    df = pd.DataFrame(data=values, columns=cols)
    start_monitor(prod_stream=df)
    