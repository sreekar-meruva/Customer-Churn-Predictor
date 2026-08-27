import pandas as pd
import numpy as np
from sklearn.metrics import fbeta_score, recall_score, precision_score, brier_score_loss
from src.simulate_deployment import generate_weeks, inject_drift_check

#Get top 3 priority features
def get_top_features(model, features):
    feature_importance = model.feature_importances_
    top_features = pd.Series(feature_importance, features).sort_values(ascending=False)
    return top_features[:3]

def get_drift_scores(baseline_stats, prod_stream, features):
    base_means = pd.Series(baseline_stats['mean'])
    base_stds = pd.Series(baseline_stats['std'])
    weekly_means = prod_stream.groupby('Week')[features].mean()
    drift_scores = (weekly_means-base_means)/base_stds
    return {
        'weekly_means': weekly_means,
        'drift_scores': drift_scores
    }

def get_performance_metrics(df, true_values):
    return {
        'F2 Score': fbeta_score(true_values, df['predictions'], beta=2),
        'Recall': recall_score(true_values, df['predictions']),
        'Precision': precision_score(true_values, df['predictions']),
        'Brier loss score': brier_score_loss(true_values, df['probabilities'])
    }

def get_model_predictions(model, threshold, batch, features):
    feature_data = batch[features]
    probabilities = model.predict_proba(feature_data)[:,1]
    predictions = (probabilities>=threshold).astype(int)
    pred_dict = {
        'record_id': batch['Record_id'],
        'probabilities': probabilities,
        'threshold': threshold,
        'predictions': predictions
    }
    pred_df = pd.DataFrame(pred_dict)
    return(pred_df)

def monitor_drift_performance(model, train_pool, prod_stream, metadata):
    features = metadata['feature_columns']
    threshold = metadata['threshold']

    if (set(features)-set(prod_stream.columns)):
        raise ValueError("Missing feature columns in production stream columns")
    
    continuous_features = [col for col in features if train_pool[col].nunique()>2]
    top_features = get_top_features(model, features)
    feature_metrics = {}
    baseline_stats = train_pool[continuous_features].agg(['mean','std'])
    for feature in top_features.index:
        feature_metrics[feature]={}
        experiment_stream = prod_stream.copy()
        experiment_stream = inject_drift_check(experiment_stream, feature)
        drift_scores = get_drift_scores(baseline_stats, experiment_stream, continuous_features)
        feature_metrics[feature]['drift_scores'] = drift_scores
        performance_records = []
        for week, week_batch in experiment_stream.groupby('Week'):
            metrics = get_performance_metrics(model, threshold, week_batch, features)
            metrics['Week']=week
            performance_records.append(metrics)

        feature_metrics[feature]['model_performance'] = performance_records
        
    return(feature_metrics)

def model_performance_report(results):
    summary_report = []
    for feature, data in results.items():
        perf_metrics = pd.DataFrame(data['model_performance'])
        pre_perf_metrics = perf_metrics.loc[(perf_metrics['Week']<15),['F2 Score','Recall','Precision','Brier loss score']].mean()
        post_perf_metrics = perf_metrics.loc[(perf_metrics['Week']>=15),['F2 Score','Recall','Precision','Brier loss score']].mean()
        summary_report.append({
            'Feature': feature,
            'pre_F2_score': pre_perf_metrics['F2 Score'], 'post_F2_score': post_perf_metrics['F2 Score'],
            'pre_recall_score': pre_perf_metrics['Recall'], 'post_recall_score': post_perf_metrics['Recall'],
            'pre_precision_score': pre_perf_metrics['Precision'], 'post_precision_score': post_perf_metrics['Precision'],
            'pre_brier_loss': pre_perf_metrics['Brier loss score'], 'post_brier_loss': post_perf_metrics['Brier loss score']
        })
    summary_df = pd.DataFrame(summary_report)
    return(summary_df)

def alert_log(drift_scores, baseline_stats, performance):
    max_drift = drift_scores.abs().to_numpy().max()

    if performance:
        threshold = baseline_stats['mean'] + (1.5*baseline_stats['std'])
        if max_drift > 1.0 and performance['Brier loss score'] > threshold:
            return "[CRITICAL] Drift detected and performance degradation confirmed"
    
    if max_drift > 1.0:
        return "[ALERT] Drift detected - verify performance impact"
    elif max_drift > 0.5:
        return "[WARNING] Mild drift detected"
    else:
        return "OK"