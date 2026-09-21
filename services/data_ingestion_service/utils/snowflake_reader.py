from services.data_ingestion_service.utils.snowflake_utils import get_snowflake_connection

def get_weeks_severity(model_version, week, range):
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    try:
        SQL_QUERY = """SELECT WEEK, SEVERITY
        FROM PERFORMANCE_LOG
        WHERE MODEL_VERSION = %s
        AND WEEK BETWEEN %s AND %s"""
        cursor.execute(SQL_QUERY,(model_version, week-range+1, week))
        response = cursor.fetchall()
        return [{'Week': record[0], 'Severity': record[1]} for record in response]
    except Exception as ex:
        raise Exception(f"Unable to fetch records due to {ex}")
    finally:
        cursor.close()
        conn.close()

def get_max_db_week(model_version):
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    try:
        SQL_QUERY = """SELECT MAX(WEEK)
        FROM PERFORMANCE_LOG
        WHERE MODEL_VERSION = %s"""
        cursor.execute(SQL_QUERY, model_version)
        response = cursor.fetchone()
        return {
            'Week': response[0]
        }
    except Exception as ex:
        raise Exception(f"Unable to get max week due to {ex}")
    finally:
        cursor.close()
        conn.close()

def get_data(table, columns, filters, limit):
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    try:
        cols = ','.join(columns)
        query = f"""SELECT {cols} FROM {table}"""
        values = []
        conditions = []
        if filters:
            for key, value in filters.items():
                if isinstance(value, list):
                    placeholders = ','.join(["%s"]*len(value))
                    conditions.append(f"{key} IN ({placeholders})")
                    values.extend(value)
                else:
                    conditions.append(f"{key} = %s")
                    values.append(value)
            query += " WHERE "+" AND ".join(conditions)
        if limit:
            query+='LIMIT %s'
            values.append(limit)
        cursor.execute(query, values)
        records = cursor.fetchall()
        return{
            'records': records
        }
    except Exception as ex:
        raise Exception(f"Unable to fetch records due to {ex}")
    finally:
        cursor.close()
        conn.close()