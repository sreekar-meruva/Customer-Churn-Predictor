import os
from snowflake.connector import connect
from dotenv import load_dotenv
import platform
platform.libc_ver = lambda *args, **kwargs: ("", "")

load_dotenv()

def get_snowflake_connection():
    return connect(
        account = os.environ["SNOWFLAKE_ACCOUNT"],
        user = os.environ["SNOWFLAKE_USER"],
        password = os.environ["SNOWFLAKE_PASSWORD"],
        role = os.environ["SNOWFLAKE_ROLE"],
        warehouse = os.environ["WAREHOUSE"],
        database = os.environ["DATABASE"],
        schema = os.environ["SCHEMA"]
    )
