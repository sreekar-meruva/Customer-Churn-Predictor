import glob
from src.utils.snowflake_utils import get_snowflake_connection

def run_ddl():
    connection = get_snowflake_connection()
    if connection:
        print("Established connection successfully!")
    cursor = connection.cursor()
    filepaths = sorted(glob.glob("sql/ddl/*.sql"))
    try:
        for filepath in filepaths:
            print(f"Running current script: {filepath} ...")
            with open(filepath) as f:
                sql_script = f.read()
            cursor.execute(sql_script)
    except Exception as e:
        raise Exception(f"Failed while running {filepath}: {e}")
    print("All the scripts Executed successfully!")
    cursor.close()
    connection.close()

def rewrite_performance_log():
    connection = get_snowflake_connection()
    cursor = connection.cursor()
    file_paths = [r"sql\ddl\004_performance_log.sql",r"sql\ddl\002_actuals.sql"]
    for file_path in file_paths:
        with open(file_path) as f:
            sql_script = f.read()
        cursor.execute(sql_script)
        print("Execution successful!")
    cursor.close()
    connection.close()

if __name__=="__main__":
    rewrite_performance_log()
    # run_ddl()