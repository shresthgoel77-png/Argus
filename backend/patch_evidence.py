import sqlite3
import json

conn = sqlite3.connect('reliability.db')
r = conn.execute("SELECT id, content FROM evidence WHERE incident_id=3 AND category='ai_rca'").fetchone()

if r:
    id, content_str = r
    content = json.loads(content_str)
    
    # Force add params
    if "recommended_remediation" not in content:
        content["recommended_remediation"] = {}
    content["recommended_remediation"]["params"] = {}
    
    # Update DB
    conn.execute("UPDATE evidence SET content = ? WHERE id = ?", (json.dumps(content), id))
    conn.commit()
    print("Direct SQLite update successful!")
else:
    print("No RCA evidence found for incident 3!")

conn.close()
