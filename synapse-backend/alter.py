import sqlite3
import time

db_path = r"c:\Academic\hackathon\synapse-backend\instance\synapse.db"
for _ in range(5):
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        c = conn.cursor()
        c.execute("ALTER TABLE notes ADD COLUMN material_id TEXT;")
        conn.commit()
        conn.close()
        print("Success: column added")
        break
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Already added: column exists")
            break
        print(f"Error: {e}")
        time.sleep(1)
