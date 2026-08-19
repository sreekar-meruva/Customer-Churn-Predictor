from src.simulate_deployment import inject_drift_check
import pandas as pd

prod_stream = pd.read_csv("Production_prepared_stream.csv")
drift_df = inject_drift_check(prod_stream,"CustServCalls")
drift_df.to_csv("Test_file.csv",index=False)