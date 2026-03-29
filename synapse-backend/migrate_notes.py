import sqlite3
import os

db_path = r"instance\synapse.db"
if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get existing columns
cursor.execute("PRAGMA table_info(notes)")
columns = [col[1] for col in cursor.fetchall()]

# Add material_id if missing
if "material_id" not in columns:
    try:
        cursor.execute("ALTER TABLE notes ADD COLUMN material_id TEXT;")
        print("Column 'material_id' added.")
    except Exception as e:
        print(f"Failed to add 'material_id': {e}")

# Add file_url if missing
if "file_url" not in columns:
    try:
        cursor.execute("ALTER TABLE notes ADD COLUMN file_url TEXT;")
        print("Column 'file_url' added.")
    except Exception as e:
        print(f"Failed to add 'file_url': {e}")

conn.commit()
conn.close()
print("Migration complete.")
