from pydantic import BaseModel
from typing import List
from fastapi import FastAPI, HTTPException, status
from contextlib import asynccontextmanager
import joblib
import json

class PredictionRequest(BaseModel):
    Record_id: str
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

model = None
metadata = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, metadata
    model = joblib.load(r"services\prediction_service\artifacts\RandomForest.joblib")
    with open(r"services\prediction_service\artifacts\model_metadata.json") as f:
        metadata = json.load(f)
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/churn_predictor/predict")
def getPrediction(payload: BatchPredictionRequest):
    if model == None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Model is not loaded.")
    if metadata == None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Metadata is not loaded.")
    threshold = metadata['threshold']
    features = metadata['feature_columns']
    dataframe = pd.DataFrame([record.model_dump() for record in payload.batch])
    record_ids = dataframe['Record_id']
    dataframe = dataframe.drop(columns=['Record_id'])
    for feature in features:
        if feature not in dataframe.columns:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unable to complete due to missing feature {feature}")
    probabilities = model.predict_proba(dataframe)[:,1]
    predictions = (probabilities>=threshold).astype(int)
    return {
        'Record_id': record_ids.tolist(),
        'Probability': probabilities.tolist(),
        'Prediction': predictions.tolist(),
        'Threshold': threshold
    }