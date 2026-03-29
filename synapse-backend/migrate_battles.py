import sqlite3

db_path = r"c:\Academic\hackathon\synapse-backend\instance\synapse.db"
conn = sqlite3.connect(db_path, timeout=10)
c = conn.cursor()

for col, coltype in [
    ("challenger_score", "INTEGER DEFAULT 0"),
    ("opponent_score", "INTEGER DEFAULT 0"),
    ("badge_awarded", "INTEGER DEFAULT 0"),
]:
    try:
        c.execute(f"ALTER TABLE battles ADD COLUMN {col} {coltype}")
        print(f"Added column: {col}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print(f"Column already exists: {col}")
        else:
            print(f"Error adding {col}: {e}")

conn.commit()
conn.close()
print("Migration complete!")
