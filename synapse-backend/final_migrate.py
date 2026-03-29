import sqlite3
import os
import time

db_path = r"instance\synapse.db"

def migrate():
    for i in range(10):
        try:
            conn = sqlite3.connect(db_path, timeout=60)
            cursor = conn.cursor()
            
            # Get columns
            cursor.execute("PRAGMA table_info(notes)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if "material_id" not in columns:
                cursor.execute("ALTER TABLE notes ADD COLUMN material_id TEXT;")
                print("Added material_id")
                
            if "file_url" not in columns:
                cursor.execute("ALTER TABLE notes ADD COLUMN file_url TEXT;")
                print("Added file_url")
                
            conn.commit()
            conn.close()
            print("Migration successful")
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                print(f"Database locked, retrying {i+1}/10...")
                time.sleep(2)
            else:
                print(f"OperationalError: {e}")
                return
        except Exception as e:
            print(f"Error: {e}")
            return

if __name__ == "__main__":
    migrate()
