from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import pandas as pd
import numpy as np
import joblib
import json

df = pd.read_csv("telecom_churn.csv")

df_train,df_production = train_test_split(df, test_size=0.4,random_state=42,stratify=df['Churn'])
df_train.to_csv("training_pool.csv",index=False)
df_production.to_csv("production_pool.csv",index=False)

model = RandomForestClassifier(random_state=42)

X = df_train.drop(['Churn'], axis=1)
y = df_train['Churn']

model.fit(X,y)

metadata = {
    "model": "RandomForestClassifier",
    "threshold": 0.25,
    "feature_columns": list(X.columns)
}

joblib.dump(model, "RandomForest.joblib")

with open("model_metadata.json", 'w') as f:
    json.dump(metadata, f)
