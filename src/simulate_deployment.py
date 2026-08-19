import pandas as pd
import numpy as np

def generate_weeks(prod_df):
    np.random.seed(42)
    date_time_offset = np.random.randint(low=0, high=182, size=len(prod_df))
    prod_df['Week'] = (date_time_offset//7)+1
    prod_df['Score_date'] = pd.to_datetime('2026-01-01')+pd.to_timedelta(date_time_offset, unit='D')
    prod_df.to_csv("Production_prepared_stream.csv", index=False)


def inject_drift_check(prod_df, feature):
    prod_df[f'Orig_{feature}'] = prod_df[feature]
    drift = round(1.5*prod_df[feature].std())

    prod_df.loc[(prod_df['Week']>=15),feature]+=drift

    before_drift_skew = round(prod_df.loc[(prod_df['Week']>=15),f'Orig_{feature}'].skew(),2)
    after_drift_skew = round(prod_df.loc[(prod_df['Week'])>=15, feature].skew(),2)

    if before_drift_skew != after_drift_skew:
        print(before_drift_skew)
        print(after_drift_skew)
        print(feature)
        raise ValueError("Drift injected skew detected.")

    return(prod_df)
    
