import pandas as pd
import json
import joblib
from src.score_and_monitor import write_performance_log
from src.score_and_monitor import get_performance_metrics
from src.validate_drift_detection import get_model_predictions, alert_log, get_drift_scores
from scripts.setup_snowflake import get_snowflake_connection
import datetime

def backfill_performance(model, metadata):
    df = pd.read_csv(r"data\processed\Production_prepared_stream.csv")
    try:
        connection = get_snowflake_connection()
        cursor = connection.cursor()
        UNIQUE_WEEKS_SCRIPT = f"SELECT DISTINCT WEEK FROM PERFORMANCE_LOG"
        cursor.execute(UNIQUE_WEEKS_SCRIPT)
        db_weeks = cursor.fetchall()[0]
        df_weeks = df['Week'].unique()
        features = metadata['feature_columns']
        threshold = metadata['threshold']
        for week in df_weeks:
            if week in db_weeks:
                continue
            df_data = df.loc[(df['Week']==week)]
            pred_df = get_model_predictions(model, threshold, df_data, features)
            initial_count = len(pred_df)
            df_data = df_data.dropna(subset='Churn')
            current_count = len(df_data)
            coverage = (current_count/initial_count)*100
            pred_churn_df = pred_df.loc[(pred_df['record_id'].isin(df_data['Record_id']))]
            perf_metrics = get_performance_metrics(pred_churn_df, df_data['Churn']) if coverage>0 else None

            cont_features = [feature for feature in features if df[feature].nunique()>2]
            drift_scores = get_drift_scores(baseline_stats=metadata['baseline_stats'],prod_stream=df, features=cont_features)
            alert_status = alert_log(drift_scores=drift_scores['drift_scores'],baseline_stats=metadata['brier_baseline_stats'],performance=perf_metrics)

            report = {
                'Week': int(week),
                'Date scored': str(datetime.date.today()),
                'Severity': alert_status,
                'Performance': perf_metrics,
                'Performance scored date': str(datetime.date.today()),
                'Week_performance_coverage': coverage,
                'Week_total_count': initial_count,
                'Week_not_null_count': current_count
            }

            write_performance_log(report, metadata)

    except Exception as e:
        raise Exception(f"Unable to backfill to table PERFORMANCE_LOG due to {e}")

    finally:
        cursor.close()
        connection.close()

if __name__=="__main__":
    with open(r"artifacts\model_metadata.json",'r') as f:
        metadata = json.load(f)
    model = joblib.load(r"artifacts\RandomForest.joblib")
    backfill_performance(model, metadata)