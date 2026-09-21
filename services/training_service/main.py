from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Optional

app = FastAPI()

class ModelRetrainRequest(BaseModel):
    drift_week: int
    range: int


@app.post("churn_predictor/retrain_model")
def retrain_model(payload: ModelRetrainRequest):
    return