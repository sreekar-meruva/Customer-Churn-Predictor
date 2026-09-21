from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import uuid
import pandas as pd
import joblib
import json

df = pd.read_csv(r"data\raw\telecom_churn.csv")
df['Record_id'] = [str(uuid.uuid4()) for _ in df.iterrows()]

df_train,df_production = train_test_split(df, test_size=0.4,random_state=42,stratify=df['Churn'])
df_train.to_csv(r"data\processed\training_pool.csv",index=False)
df_production.to_csv(r"data\processed\production_pool.csv",index=False)

model = RandomForestClassifier(random_state=42)

X = df_train.drop(['Churn','Record_id'], axis=1)
y = df_train['Churn']

model.fit(X,y)

metadata = {
    "model": "RandomForestClassifier",
    "threshold": 0.25,
    "feature_columns": list(X.columns),
    "model_deployment_week": 1
}

joblib.dump(model, r"artifacts\RandomForest.joblib")

with open(r"artifacts\model_metadata.json", 'w') as f:
    json.dump(metadata, f)
