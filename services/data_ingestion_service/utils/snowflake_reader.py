from api.utils.snowflake_utils import get_snowflake_connection

def get_weeks_severity(model_version, week, range):
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    try:
        SQL_QUERY = """SELECT WEEK, SEVERITY
        FROM PERFORMANCE_LOG
        WHERE MODEL_VERSION = %s
        AND WEEK BETWEEN %s AND %s"""
        cursor.execute(SQL_QUERY,(model_version, week-range-1, week))
        response = cursor.fetchall()
        return [{'Week': record[0], 'Severity': record[1]} for record in response]
    except Exception as ex:
        raise Exception(f"Unable to fetch records due to {ex}")
    finally:
        cursor.close()
        conn.close()
