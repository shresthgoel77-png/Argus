import sqlite3
import os
db_path = "test.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF;")
    conn.execute("DROP TABLE IF EXISTS bot_interactions;")
    # Reset indices for AIAnalysis etc if they were messed up, but they are exactly same structural indexes implicitly, so we can ignore. 
    # Just update alembic_version
    conn.execute("UPDATE alembic_version SET version_num = '5a70e50d3c97';")
    conn.commit()
    conn.close()
    print("Database reset successfully.")
