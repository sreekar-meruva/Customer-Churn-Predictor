import pandas as pd
from scripts.setup_snowflake import get_snowflake_connection

def get_unique_weeks(table_name):
    week=26
    connection = get_snowflake_connection()
    cursor = connection.cursor()
    SQL_QUERY = f"SELECT DISTINCT WEEK FROM {table_name}"
    cursor.execute(SQL_QUERY)
    result = [row[0] for row in cursor.fetchall()]
    print(result)
    if week in result:
        print("True")
    cursor.close()
    connection.close()

if __name__=="__main__":
    get_unique_weeks("PERFORMANCE_LOG")
