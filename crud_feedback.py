# pip install mysql-connector-python flask flask-cors requests
# pip install mysql-connector-python
import mysql.connector
import uuid

# Configurar conexión (igual que en tu ejemplo)
conn = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="contrasena",
    database="testdb",
    port=3306
)
cursor = conn.cursor(dictionary=True)

# CREATE
def create_feedback(session_id, item_type, feedback, intent, emotion,
                    item_id=None, provider="spotify", provider_playlist_id=None,
                    confidence=None, reason_code=None, comment=None,
                    latency_ms=None, retries=None, client_device=None,
                    client_version=None, trace_id=None, supersedes_event_id=None):
    feedback_id = str(uuid.uuid4())
    sql = """
        INSERT INTO feedback_events (
          feedback_id, session_id, item_type, item_id, provider, provider_playlist_id,
          feedback, reason_code, comment, intent, emotion, confidence,
          latency_ms, retries, client_device, client_version, trace_id, supersedes_event_id
        ) VALUES (
          %s, %s, %s, %s, %s, %s,
          %s, %s, %s, %s, %s, %s,
          %s, %s, %s, %s, %s, %s
        )
    """
    vals = [feedback_id, session_id, item_type, item_id, provider, provider_playlist_id,
            feedback, reason_code, comment, intent, emotion, confidence,
            latency_ms, retries, client_device, client_version, trace_id, supersedes_event_id]
    cursor.execute(sql, vals)
    conn.commit()
    return feedback_id

# READ ALL
def read_feedbacks():
    cursor.execute("SELECT * FROM feedback_events ORDER BY created_at DESC")
    return cursor.fetchall()

# UPDATE (parcial)
def update_feedback(feedback_id, updates: dict):
    if not updates:
        return 0
    sets = []
    vals = []
    for k, v in updates.items():
        sets.append(f"{k}=%s")
        vals.append(v)
    vals.append(feedback_id)
    sql = f"UPDATE feedback_events SET {', '.join(sets)} WHERE feedback_id=%s"
    cursor.execute(sql, vals)
    conn.commit()
    return cursor.rowcount

# DELETE
def delete_feedback(feedback_id):
    cursor.execute("DELETE FROM feedback_events WHERE feedback_id=%s", (feedback_id,))
    conn.commit()
    return cursor.rowcount

# Ejemplo rápido
if __name__ == "__main__":
    new_id = create_feedback(
        session_id="sess_demo",
        item_type="playlist",
        feedback="like",
        intent="maintain",
        emotion="joy",
        item_id="pl_joy_001",
        confidence=0.85,
        client_device="web",
        client_version="v1.0.0"
    )
    print("CREATED:", new_id)
    print("LIST:", read_feedbacks())
    print("UPDATED rows:", update_feedback(new_id, {"feedback": "dislike", "reason_code": "not_my_style"}))
    print("DELETED rows:", delete_feedback(new_id))

    cursor.close()
    conn.close()

