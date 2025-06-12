import os
from dotenv import load_dotenv
import mysql.connector
load_dotenv()

H = os.getenv("MYSQL_HOST")
D = os.getenv("MYSQL_DB")
U = os.getenv("MYSQL_USER")
P = os.getenv("MYSQL_PASSWORD")

conn = mysql.connector.connect(
    host = H,
    database = D,
    user = U,
    password = P
)

cursor = conn.cursor()

cursor.execute('select * from employee;')
t = cursor.fetchall()
for i in t:
    if int(i[0][3:]) >= 46:
        cursor.execute(f'UPDATE employee SET category_type = "D" WHERE employee_ID = "{i[0]}";')
        conn.commit()