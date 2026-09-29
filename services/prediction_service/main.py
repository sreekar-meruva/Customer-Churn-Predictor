from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException, status, UploadFile, File, Form
import pandas as pd
from contextlib import asynccontextmanager
import joblib
import json

class PredictionRequest(BaseModel):
    Record_id: Optional[str] = None
    AccountWeeks: float
    ContractRenewal: int
    DataPlan: int
    DataUsage: float
    CustServCalls: float
    DayMins: float
    DayCalls: float
    MonthlyCharge: float
    OverageFee: float
    RoamMins: float

class BatchPredictionRequest(BaseModel):
    batch: List[PredictionRequest]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = joblib.load(r"artifacts/RandomForest.joblib")
    with open(r"artifacts/model_metadata.json") as f:
        app.state.metadata = json.load(f)
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/churn_predictor/predict")
def getPrediction(payload: BatchPredictionRequest):
    if app.state.model == None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Model is not loaded.")
    if app.state.metadata == None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Metadata is not loaded.")
    threshold = app.state.metadata['threshold']
    features = app.state.metadata['feature_columns']
    dataframe = pd.DataFrame([record.model_dump() for record in payload.batch])
    record_ids = dataframe['Record_id']
    dataframe = dataframe.drop(columns=['Record_id'])
    for feature in features:
        if feature not in dataframe.columns:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unable to complete due to missing feature {feature}")
    probabilities = app.state.model.predict_proba(dataframe)[:,1]
    predictions = (probabilities>=threshold).astype(int)
    return {
        'Record_id': record_ids.tolist() if record_ids else None,
        'Probability': probabilities.tolist(),
        'Prediction': predictions.tolist(),
        'Threshold': threshold
    }

@app.get("/churn_predictor/metadata")
def request_metadata(request: Request):
    return request.app.state.metadata

@app.post("/churn_predictor/update-artifacts")
async def update_artifacts(request: Request,model_file: UploadFile, metadata: str = Form(...)):
    try:
        contents = await model_file.read()
        with open(r"artifacts/RandomForest.joblib","wb") as f:
            f.write(contents)
        request.app.state.model = joblib.load(r"artifacts/RandomForest.joblib")
        request.app.state.metadata = json.loads(metadata)
        with open(r"artifacts/model_metadata.json",'w') as f:
            json.dump(request.app.metadata, f)
        return {
            "status": "Reload complete",
            "model_version": request.app.state.metadata['model']
        }
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unable to update the records due to {ex}")

@app.post("/churn_predictor/update-metadata")
def update_metadata(request: Request, metadata: str = Form(...)):
    try:
        new_fields = json.loads(metadata)
        request.app.state.metadata = {**request.app.state.metadata,**new_fields}
        with open(r"artifacts/model_metadata.json","w") as f:
            json.dumps(request.app.state.metadata,f)
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unable to update metadata due to {ex}")