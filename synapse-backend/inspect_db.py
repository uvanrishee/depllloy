import sqlite3
import os

db_path = r"c:\Academic\hackathon\synapse-backend\instance\synapse.db"

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def print_table(name):
    print(f"\n--- {name} ---")
    rows = cur.execute(f"SELECT * FROM {name} LIMIT 5").fetchall()
    for row in rows:
        print(dict(row))
        
print_table("users")
print_table("classrooms")
print_table("enrollments")
print_table("quiz_attempts")
print_table("quizzes")

conn.close()
