from flask import Flask, request, jsonify
import mysql.connector
import uuid

# Config de conexión (igual a tu ejemplo)
db_config = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "contrasena",
    "database": "testdb",
    "port": 3306
}

app = Flask(__name__)

def get_db_connection():
    return mysql.connector.connect(**db_config)

# --- Enums válidos (validación básica)
VALID_ITEM_TYPE = {"playlist", "track"}
VALID_FEEDBACK = {"like", "dislike", "skip", "save", "share", "undo"}
VALID_INTENT = {"maintain", "change"}
VALID_EMOTION = {"joy", "sadness", "anger"}

def ensure_uuid(s):
    try:
        return str(uuid.UUID(str(s)))
    except Exception:
        raise ValueError("feedback_id must be a valid UUID string")

def validate_enums(data):
    if "item_type" in data and data["item_type"] not in VALID_ITEM_TYPE:
        raise ValueError(f"item_type must be one of {sorted(VALID_ITEM_TYPE)}")
    if "feedback" in data and data["feedback"] not in VALID_FEEDBACK:
        raise ValueError(f"feedback must be one of {sorted(VALID_FEEDBACK)}")
    if "intent" in data and data["intent"] not in VALID_INTENT:
        raise ValueError(f"intent must be one of {sorted(VALID_INTENT)}")
    if "emotion" in data and data["emotion"] not in VALID_EMOTION:
        raise ValueError(f"emotion must be one of {sorted(VALID_EMOTION)}")

# --- LIST (GET /feedback-events) con filtros y paginación
@app.route("/feedback-events", methods=["GET"])
def list_feedback_events():
    try:
        user_session = request.args.get("session_id")
        item_type = request.args.get("item_type")
        feedback = request.args.get("feedback")
        intent = request.args.get("intent")
        emotion = request.args.get("emotion")
        page = max(1, request.args.get("page", default=1, type=int))
        page_size = max(1, min(request.args.get("page_size", default=50, type=int), 200))

        filters = []
        params = []
        if user_session:
            filters.append("session_id = %s")
            params.append(user_session)
        if item_type:
            validate_enums({"item_type": item_type})
            filters.append("item_type = %s")
            params.append(item_type)
        if feedback:
            validate_enums({"feedback": feedback})
            filters.append("feedback = %s")
            params.append(feedback)
        if intent:
            validate_enums({"intent": intent})
            filters.append("intent = %s")
            params.append(intent)
        if emotion:
            validate_enums({"emotion": emotion})
            filters.append("emotion = %s")
            params.append(emotion)

        where_sql = (" WHERE " + " AND ".join(filters)) if filters else ""

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute(f"SELECT COUNT(*) AS total FROM feedback_events{where_sql}", params)
        total = cur.fetchone()["total"]

        params2 = params + [page_size, (page - 1) * page_size]
        cur.execute(f"""
            SELECT * FROM feedback_events
            {where_sql}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, params2)
        rows = cur.fetchall()

        cur.close()
        conn.close()
        return jsonify({"data": rows, "page": page, "page_size": page_size, "total": total}), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500

# --- GET by id (GET /feedback-events/<feedback_id>)
@app.route("/feedback-events/<feedback_id>", methods=["GET"])
def get_feedback_event(feedback_id):
    try:
        feedback_id = ensure_uuid(feedback_id)
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM feedback_events WHERE feedback_id = %s", (feedback_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "Feedback event no encontrado"}), 404
        return jsonify(row), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500

# --- CREATE (POST /feedback-events)
@app.route("/feedback-events", methods=["POST"])
def create_feedback_event():
    try:
        data = request.get_json(force=True) or {}

        required = ["session_id", "item_type", "feedback", "intent", "emotion"]
        missing = [k for k in required if not data.get(k)]
        if missing:
            return jsonify({"error": f"Faltan campos requeridos: {missing}"}), 400

        validate_enums(data)

        # validar confidence
        if data.get("confidence") is not None:
            try:
                c = float(data["confidence"])
                if c < 0 or c > 1:
                    return jsonify({"error": "confidence debe estar entre 0 y 1"}), 400
            except Exception:
                return jsonify({"error": "confidence debe ser numérico"}), 400

        feedback_id = ensure_uuid(data.get("feedback_id") or str(uuid.uuid4()))
        provider = data.get("provider", "spotify")

        cols = [
            "feedback_id", "session_id", "item_type", "item_id", "provider", "provider_playlist_id",
            "feedback", "reason_code", "comment", "intent", "emotion", "confidence",
            "latency_ms", "retries", "client_device", "client_version", "trace_id", "supersedes_event_id"
        ]
        vals = [
            feedback_id, data["session_id"], data["item_type"], data.get("item_id"),
            provider, data.get("provider_playlist_id"),
            data["feedback"], data.get("reason_code"), data.get("comment"),
            data["intent"], data["emotion"], data.get("confidence"),
            data.get("latency_ms"), data.get("retries"),
            data.get("client_device"), data.get("client_version"),
            data.get("trace_id"), data.get("supersedes_event_id")
        ]

        placeholders = ", ".join(["%s"] * len(cols))
        sql = f"INSERT INTO feedback_events ({', '.join(cols)}) VALUES ({placeholders})"

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(sql, vals)
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"feedback_id": feedback_id, "message": "Feedback event creado"}), 201

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except mysql.connector.Error as me:
        return jsonify({"error": f"MySQL error: {str(me)}"}), 500
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500

# --- UPDATE (PUT /feedback-events/<feedback_id>)
@app.route("/feedback-events/<feedback_id>", methods=["PUT"])
def update_feedback_event(feedback_id):
    try:
        feedback_id = ensure_uuid(feedback_id)
        data = request.get_json(force=True) or {}

        allowed = {
            "session_id", "item_type", "item_id", "provider", "provider_playlist_id",
            "feedback", "reason_code", "comment", "intent", "emotion", "confidence",
            "latency_ms", "retries", "client_device", "client_version", "trace_id",
            "supersedes_event_id"
        }
        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            return jsonify({"error": "No hay campos válidos para actualizar"}), 400

        validate_enums(updates)
        if "confidence" in updates and updates["confidence"] is not None:
            try:
                c = float(updates["confidence"])
                if c < 0 or c > 1:
                    return jsonify({"error": "confidence debe estar entre 0 y 1"}), 400
            except Exception:
                return jsonify({"error": "confidence debe ser numérico"}), 400

        sets = []
        params = []
        for k, v in updates.items():
            sets.append(f"{k} = %s")
            params.append(v)
        params.append(feedback_id)

        sql = f"UPDATE feedback_events SET {', '.join(sets)} WHERE feedback_id = %s"

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        affected = cur.rowcount
        cur.close()
        conn.close()

        if affected == 0:
            return jsonify({"error": "Feedback event no encontrado"}), 404
        return jsonify({"message": "Feedback event actualizado"}), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except mysql.connector.Error as me:
        return jsonify({"error": f"MySQL error: {str(me)}"}), 500
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500

# --- DELETE (DELETE /feedback-events/<feedback_id>)
@app.route("/feedback-events/<feedback_id>", methods=["DELETE"])
def delete_feedback_event(feedback_id):
    try:
        feedback_id = ensure_uuid(feedback_id)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM feedback_events WHERE feedback_id = %s", (feedback_id,))
        conn.commit()
        affected = cur.rowcount
        cur.close()
        conn.close()
        if affected == 0:
            return jsonify({"error": "Feedback event no encontrado"}), 404
        return jsonify({"message": "Feedback event eliminado"}), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except mysql.connector.Error as me:
        return jsonify({"error": f"MySQL error: {str(me)}"}), 500
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500

if __name__ == "__main__":
    # Igual que tu ejemplo: http://127.0.0.1:8000
    app.run(host="0.0.0.0", port=8000, debug=True)

