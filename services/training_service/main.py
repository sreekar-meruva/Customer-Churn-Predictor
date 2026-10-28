from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
from scripts.model_race import model_train, update_artifacts, trigger_monitor

app = FastAPI()

class ModelRetrainRequest(BaseModel):
    drift_week: int
    range: Optional[int] = 18


@app.post("/churn_predictor/retrain_model")
def retrain_model(payload: ModelRetrainRequest):
    try:
        model_train(payload.drift_week, payload.range)
    except Exception as ex:
        raise Exception(f"Unable to trigger model train due to {ex}")
    return {
        'detail': "Model train triggered check log results."
    }

@app.get("/churn_predictor/{token_id}/approve", response_class=HTMLResponse)
def approve_request(token_id: str):
    try:
        update_artifacts(token_id)
        trigger_monitor()
        return "<h3>Model approved and deployed.</h3>"
    except Exception as ex:
        return HTMLResponse(f"<h3>Approval failed: {ex}</h3>", status_code=400)