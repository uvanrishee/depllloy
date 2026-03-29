import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'synapse.db')
print(f"Opening DB at {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get columns
    cursor.execute("PRAGMA table_info(notes)")
    cols = [col[1] for col in cursor.fetchall()]
    
    # Alter if necessary
    if "material_id" not in cols:
        cursor.execute("ALTER TABLE notes ADD COLUMN material_id TEXT;")
        print("Added material_id")
    if "file_url" not in cols:
        cursor.execute("ALTER TABLE notes ADD COLUMN file_url TEXT;")
        print("Added file_url")
    if "classroom_id" not in cols:
        cursor.execute("ALTER TABLE notes ADD COLUMN classroom_id TEXT;")
        print("Added classroom_id")
        
    conn.commit()
    conn.close()
    print("DB fix completed.")
except Exception as e:
    print(f"Error fixing DB: {e}")
