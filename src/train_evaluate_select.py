import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import recall_score, precision_score, fbeta_score, brier_score_loss
from sklearn.calibration import calibration_curve
from xgboost import XGBClassifier
import numpy as np
import matplotlib.pyplot as plt
import pprint

df = pd.read_csv("telecom_churn.csv")
class_balance = df['Churn'].value_counts()

X = df.drop(["Churn"],axis=1)
y = df["Churn"]

skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=12)
splits = skf.split(X,y)
scaler = StandardScaler()

def check_outliers(outliers, std):
    max_gap = 0.0
    for indx in range(1,len(outliers)):
        max_gap = max(max_gap,outliers.iloc[indx-1]-outliers.iloc[indx])
    if (max_gap/std) > 3:
        return(True)
    return(False)

def checkSingleOutlier(outlier, std, boundary):
    gap = abs(outlier-boundary)
    if gap/std > 3:
        return("Robust outlier")
    return("Standard outlier")

def scalingOptions(train_data):
    features_scaling = {}
    for feature in train_data.columns:
        if(train_data[feature].nunique()==2):
            continue
        describe = train_data[feature].describe()
        IQR = describe['75%']-describe['25%']
        lower_boundary = describe['25%']-(1.5*IQR)
        upper_boundary = describe['75%']+(1.5*IQR)
        outliers = ((train_data[feature]<lower_boundary) | (train_data[feature]>upper_boundary)).sum()
        if outliers:
            outliers_values = train_data[feature][(train_data[feature]<lower_boundary)|(train_data[feature]>upper_boundary)]
            outliers_values = outliers_values.sort_values(ascending=False)
            std = train_data[feature].describe()['std']
            if(outliers<2):
                features_scaling[feature] = checkSingleOutlier(
                    outliers_values.iloc[0],
                    std,
                    lower_boundary if outliers_values.iloc[0]<lower_boundary else upper_boundary
                )
                continue
            right_check = check_outliers(outliers_values.head(5),std)
            left_check = check_outliers(outliers_values.tail(5),std)
            if right_check or left_check:
                features_scaling[feature] = 'Robust Scaler'
            else:
                features_scaling[feature] = 'Standard Scaler'
        else:
            features_scaling[feature] = 'Standard Scaler'
    return features_scaling

log_model = LogisticRegression()
rft_model = RandomForestClassifier()
xgb_model = XGBClassifier()

results = {}

def compute_metrics(y_actual, y_pred):
    recall = recall_score(y_actual, y_pred)
    precision = precision_score(y_actual, y_pred)
    f2_score = fbeta_score(y_actual, y_pred, beta=2)
    metrics = {
        "recall": recall,
        "precision": precision,
        "f2_score": f2_score
    }
    return(metrics)

def find_optimal_threshold(y_actual, y_probs):
    thresholds = np.arange(0.1, 0.9, 0.05)
    max_f2 = 0 
    optimal_threshold = 0
    for threshold in thresholds:
        y_preds = (y_probs>=threshold).astype(int)
        f2_score = fbeta_score(y_actual, y_preds,beta=2)
        if max_f2<f2_score:
            max_f2 = f2_score
            optimal_threshold = threshold
    return {
        "threshold": optimal_threshold,
        "f2_score": max_f2
    }

def generate_calibration_graph(y_actual, y_probs, model_name):
    plt.plot(y_actual, y_probs)
    plt.plot([0,1],[0,1])
    plt.title(f"Calibration curve for {model_name}")
    plt.xlabel("Probability predictions")
    plt.ylabel("True values in bin")
    plt.legend()
    plt.show()

y_actual = []
log_probs = []
rft_probs = []
xgb_probs = []
feature_importance=[]
for indx,(train_indx, val_indx) in enumerate(splits):
    X_train_data = X.iloc[train_indx]
    y_train_data = y.iloc[train_indx]
    X_val_data = X.iloc[val_indx]
    y_val_data = y.iloc[val_indx]
    #Based on the results, we see that the data has no extreme outliers resulting us to use the Standard scaler
    scaling_cols = ["AccountWeeks","DataUsage","CustServCalls","DayMins","DayCalls","MonthlyCharge","OverageFee","RoamMins"]
    rem_cols = [col for col in X_train_data.columns if col not in scaling_cols]
    X_train_scaled = scaler.fit_transform(X_train_data[scaling_cols])
    X_train_scaled_df = pd.DataFrame(
        data=X_train_scaled,
        columns=scaling_cols,
        index=X_train_data.index
    )
    X_train_scaled_df = pd.concat([X_train_scaled_df,X_train_data[rem_cols]],axis=1)
    X_val_scaled = scaler.transform(X_val_data[scaling_cols])
    X_val_scaled_df = pd.DataFrame(
        data = X_val_scaled,
        columns = scaling_cols,
        index=X_val_data.index
    )
    X_val_scaled_df = pd.concat([X_val_scaled_df, X_val_data[rem_cols]],axis=1)
    log_model.fit(X_train_scaled_df, y_train_data)
    y_log_prob = log_model.predict_proba(X_val_scaled_df)[:,1]
    rft_model.fit(X_train_data,y_train_data)
    feature_importance.append(rft_model.feature_importances_)
    y_rft_prob = rft_model.predict_proba(X_val_data)[:,1]
    xgb_model.fit(X_train_data, y_train_data)
    y_xgb_prob = xgb_model.predict_proba(X_val_data)[:,1]
    #Converting all the probabilites to one list
    y_actual.extend(y_val_data)
    log_probs.extend(y_log_prob)
    rft_probs.extend(y_rft_prob)
    xgb_probs.extend(y_xgb_prob)

avg_importances = np.mean(feature_importance,axis=0)
avg_importances = pd.Series(avg_importances,index=X.columns).sort_values(ascending=False)

print(avg_importances)

y_actual = np.array(y_actual)
log_probs = np.array(log_probs)
rft_probs = np.array(rft_probs)
xgb_probs = np.array(xgb_probs)

#Find optimal threshold
log_threshold = find_optimal_threshold(y_actual, log_probs)
rft_threshold = find_optimal_threshold(y_actual, rft_probs)
xgb_threshold = find_optimal_threshold(y_actual, xgb_probs)

print("Logistic Threshold: "+str(log_threshold))
print("Random Forest Threshold: "+str(rft_threshold))
print("XG Boost Threshold: "+str(xgb_threshold))

#Generate predictions based on optimal threshold
log_preds = (log_probs>=log_threshold["threshold"]).astype(int)
rft_preds = (rft_probs>=rft_threshold["threshold"]).astype(int)
xgb_preds = (xgb_probs>=xgb_threshold["threshold"]).astype(int)

#Generate recall scores based on predictions
log_optimal_recall = recall_score(y_actual, log_preds)
rft_optimal_recall = recall_score(y_actual, rft_preds)
xgb_optimal_recall = recall_score(y_actual, xgb_preds)

#Generate precision scores based on predictions
log_optimal_precision = precision_score(y_actual, log_preds)
rft_optimal_precision = precision_score(y_actual, rft_preds)
xgb_optimal_precision = precision_score(y_actual, xgb_preds)

recall_precision = {
    "Logistic":{
        "precision": log_optimal_precision,
        "recall": log_optimal_recall
    },
    "Random Forest":{
        "precision": rft_optimal_precision,
        "recall": rft_optimal_recall
    },
    "XG Boost":{
        "precision": xgb_optimal_precision,
        "recall": xgb_optimal_recall
    }
}

log_true, log_prob_pred = calibration_curve(np.array(y_actual), np.array(log_probs), n_bins=10)
rft_true, rft_prob_pred = calibration_curve(np.array(y_actual), np.array(rft_probs), n_bins=10)
xgb_true, xgb_prob_pred = calibration_curve(np.array(y_actual), np.array(xgb_probs),n_bins=10)

log_brier_loss = brier_score_loss(y_actual, log_probs)
rft_brier_loss = brier_score_loss(y_actual, rft_probs)
xgb_brier_loss = brier_score_loss(y_actual, xgb_probs)

print("Logistic Brier Loss: "+str(log_brier_loss))
print("Random Forest Brier Loss: "+str(rft_brier_loss))
print("XG Boost Brier Loss: "+str(xgb_brier_loss) )