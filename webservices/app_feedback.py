# app_feedback.py
# Flask API para CRUD de feedback_events (MySQL)
# Requisitos:
#   pip install Flask mysql-connector-python
#
# Ejecutar:
#   python app_feedback.py
# Servidor:
#   http://127.0.0.1:8000

from flask import Flask, request, jsonify
import mysql.connector
import uuid

# -----------------------------
# Configuración de la conexión
# -----------------------------
DB = dict(
    host="127.0.0.1",
    user="root",
    password="contrasena",
    database="testdb",
    port=3306,
)

def get_db():
    return mysql.connector.connect(**DB)

# -----------------------------
# App Flask
# -----------------------------
app = Flask(__name__)

API_VERSION = "1.0.0"

# Enums permitidos (misma semántica que el DDL)
VALID_ITEM_TYPE = {"playlist", "track"}
VALID_FEEDBACK = {"like", "dislike", "skip", "save", "share", "undo"}
VALID_INTENT = {"maintain", "change"}
VALID_EMOTION = {"joy", "sadness", "anger"}

# -----------------------------
# Utilidades
# -----------------------------
def ensure_uuid(val: str) -> str:
    """Valida/normaliza UUID (string). Lanza ValueError si es inválido."""
    try:
        return str(uuid.UUID(str(val)))
    except Exception:
        raise ValueError("feedback_id must be a valid UUID string")

def validate_enums(data: dict):
    """Valida que los campos enum (si vienen) estén dentro del dominio permitido."""
    if "item_type" in data and data["item_type"] is not None:
        if data["item_type"] not in VALID_ITEM_TYPE:
            raise ValueError(f"item_type must be one of {sorted(VALID_ITEM_TYPE)}")
    if "feedback" in data and data["feedback"] is not None:
        if data["feedback"] not in VALID_FEEDBACK:
            raise ValueError(f"feedback must be one of {sorted(VALID_FEEDBACK)}")
    if "intent" in data and data["intent"] is not None:
        if data["intent"] not in VALID_INTENT:
            raise ValueError(f"intent must be one of {sorted(VALID_INTENT)}")
    if "emotion" in data and data["emotion"] is not None:
        if data["emotion"] not in VALID_EMOTION:
            raise ValueError(f"emotion must be one of {sorted(VALID_EMOTION)}")

def validate_confidence(val):
    """Valida que confidence ∈ [0,1] si viene."""
    if val is None:
        return
    try:
        c = float(val)
    except Exception:
        raise ValueError("confidence debe ser numérico")
    if c < 0 or c > 1:
        raise ValueError("confidence debe estar entre 0 y 1")

# -----------------------------
# Health / Version
# -----------------------------
@app.get("/")
def root():
    return jsonify({"name": "feedback-events", "version": API_VERSION, "ok": True})

@app.get("/version")
def version():
    return jsonify({"version": API_VERSION})

@app.get("/health")
def health():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        conn.close()
        return jsonify({"status": "ok"}), 200
    except Exception as ex:
        return jsonify({"status": "error", "detail": str(ex)}), 500

# -----------------------------
# Endpoints CRUD
# -----------------------------

# LIST – GET /feedback-events (con filtros y paginación)
@app.get("/feedback-events")
def list_feedback_events():
    try:
        q = request.args
        filters, params = [], []

        # Filtros opcionales
        for key in ("session_id", "item_type", "feedback", "intent", "emotion"):
            v = q.get(key)
            if v:
                validate_enums({key: v})
                filters.append(f"{key} = %s")
                params.append(v)

        where_sql = (" WHERE " + " AND ".join(filters)) if filters else ""

        # Paginación
        page = max(1, q.get("page", type=int) or 1)
        size = max(1, min(q.get("page_size", type=int) or 50, 200))
        offset = (page - 1) * size

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # Total
        cur.execute(f"SELECT COUNT(*) AS total FROM feedback_events{where_sql}", params)
        total = cur.fetchone()["total"]

        # Datos
        cur.execute(
            f"""SELECT * FROM feedback_events
                {where_sql}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """,
            params + [size, offset],
        )
        rows = cur.fetchall()

        cur.close()
        conn.close()

        return jsonify({"data": rows, "page": page, "page_size": size, "total": total}), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500

# GET – /feedback-events/<feedback_id>
@app.get("/feedback-events/<feedback_id>")
def get_feedback_event(feedback_id):
    try:
        feedback_id = ensure_uuid(feedback_id)
        conn = get_db()
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

# CREATE – POST /feedback-events
@app.post("/feedback-events")
def create_feedback_event():
    try:
        d = request.get_json(force=True) or {}

        # Requeridos mínimos
        required = ["session_id", "item_type", "feedback", "intent", "emotion"]
        missing = [k for k in required if not d.get(k)]
        if missing:
            return jsonify({"error": f"Faltan campos requeridos: {missing}"}), 400

        # Validaciones
        validate_enums(d)
        validate_confidence(d.get("confidence"))

        # UUID
        fid = ensure_uuid(d.get("feedback_id") or str(uuid.uuid4()))

        cols = [
            "feedback_id", "session_id",
            "item_type", "item_id", "provider", "provider_playlist_id",
            "feedback", "reason_code", "comment",
            "intent", "emotion", "confidence",
            "latency_ms", "retries",
            "client_device", "client_version", "trace_id",
            "supersedes_event_id",
        ]
        vals = [
            fid, d["session_id"],
            d["item_type"], d.get("item_id"), d.get("provider", "spotify"), d.get("provider_playlist_id"),
            d["feedback"], d.get("reason_code"), d.get("comment"),
            d["intent"], d["emotion"], d.get("confidence"),
            d.get("latency_ms"), d.get("retries"),
            d.get("client_device"), d.get("client_version"), d.get("trace_id"),
            d.get("supersedes_event_id"),
        ]
        placeholders = ", ".join(["%s"] * len(cols))

        conn = get_db()
        cur = conn.cursor()
        cur.execute(f"INSERT INTO feedback_events ({', '.join(cols)}) VALUES ({placeholders})", vals)
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"feedback_id": fid, "message": "Feedback event creado"}), 201

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except mysql.connector.Error as me:
        return jsonify({"error": f"MySQL error: {me}"}), 500
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500

# UPDATE – PUT /feedback-events/<feedback_id> (actualiza parcial)
@app.put("/feedback-events/<feedback_id>")
def update_feedback_event(feedback_id):
    try:
        feedback_id = ensure_uuid(feedback_id)
        d = request.get_json(force=True) or {}

        allowed = {
            "session_id",
            "item_type", "item_id", "provider", "provider_playlist_id",
            "feedback", "reason_code", "comment",
            "intent", "emotion", "confidence",
            "latency_ms", "retries",
            "client_device", "client_version", "trace_id",
            "supersedes_event_id",
        }
        updates = {k: v for k, v in d.items() if k in allowed}
        if not updates:
            return jsonify({"error": "No hay campos válidos para actualizar"}), 400

        validate_enums(updates)
        if "confidence" in updates:
            validate_confidence(updates["confidence"])

        sets = ", ".join([f"{k} = %s" for k in updates.keys()])
        params = list(updates.values()) + [feedback_id]

        conn = get_db()
        cur = conn.cursor()
        cur.execute(f"UPDATE feedback_events SET {sets} WHERE feedback_id = %s", params)
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
        return jsonify({"error": f"MySQL error: {me}"}), 500
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500

# DELETE – /feedback-events/<feedback_id>
@app.delete("/feedback-events/<feedback_id>")
def delete_feedback_event(feedback_id):
    try:
        feedback_id = ensure_uuid(feedback_id)
        conn = get_db()
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
        return jsonify({"error": f"MySQL error: {me}"}), 500
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500

# -----------------------------
# Arranque
# -----------------------------
if __name__ == "__main__":
    # Mismo estilo que ws_crud.py del repo
    app.run(host="0.0.0.0", port=8000, debug=True)
