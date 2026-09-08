from api.utils.snowflake_utils import get_snowflake_connection
import pandas as pd

def insert_dataframe(df, table_name):
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    columns = ', '.join(df.columns)
    try:
        placeholders = ", ".join(['%s'] * len(df.columns))
        INSERT_QUERY = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        values = [tuple(row) for row in df.itertuples(index=False)]
        cursor.executemany(INSERT_QUERY, values)
        return(f'Insert query run successfully completed for {table_name}!')
    except Exception as e:
        raise Exception(f"Unable to insert the records to table due to {e}")
    finally:
        cursor.close()
        conn.close()