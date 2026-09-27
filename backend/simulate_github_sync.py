import sqlite3
import uuid
from app.integrations.github.install_state import generate_install_state

def main():
    conn = sqlite3.connect("test.db")
    c = conn.cursor()
    c.execute("SELECT id FROM users LIMIT 1")
    row = c.fetchone()
    if row:
        user_id_raw = row[0]
        try:
            if isinstance(user_id_raw, bytes):
                user_id = uuid.UUID(bytes=user_id_raw)
            else:
                user_id = uuid.UUID(user_id_raw)
            state = generate_install_state(user_id)
            print("STATE_TOKEN:", state)
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    main()
