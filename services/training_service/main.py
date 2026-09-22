from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Optional
from training_service.scripts.model_race import model_train

app = FastAPI()

class ModelRetrainRequest(BaseModel):
    drift_week: int
    range: Optional[int] = 18


@app.post("churn_predictor/retrain_model")
def retrain_model(payload: ModelRetrainRequest):
    try:
        model_train(payload.drift_week, payload.range)
    except Exception as ex:
        raise Exception(f"Unable to trigger model train due to {ex}")
    return {
        'detail': "Model train triggered check log results."
    }