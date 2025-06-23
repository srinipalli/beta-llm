from mysql.connector import connect 
from os import getenv
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return connect(
        host=getenv("MYSQL_HOST"),
        user=getenv("MYSQL_USER"),
        password=getenv("MYSQL_PASSWORD"),
        database=getenv("MYSQL_DB")
    )