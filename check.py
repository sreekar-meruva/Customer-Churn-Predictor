import requests
import pandas as pd
import json

BASE_URL = "http://127.0.0.1:8000"

with open(f"artifacts\model_metadata.json") as f:
    metadata = json.load(f)

dataframe = pd.read_csv(f"data\processed\Production_prepared_stream.csv")
dataframe = dataframe.loc[(dataframe['Week']==26)]
features = ['Record_id']+metadata['feature_columns']
dataframe = dataframe[features]
data_dict = dataframe.to_dict(orient="records")

URL = BASE_URL+"/churn_predictor/predict"

payload = {
    "batch": data_dict
}

response = requests.post(URL, json=payload)

resp = response.json()
resp_df = pd.DataFrame(resp)
print(resp_df)