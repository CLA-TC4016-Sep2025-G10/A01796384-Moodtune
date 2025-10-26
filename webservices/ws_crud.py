from flask import Flask, request, jsonify
import mysql.connector

# Configuración de la conexión a MySQL
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

@app.route("/jedis", methods=["GET"])
def get_jedis():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM jedi")
    jedis = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(jedis)

@app.route("/jedis/<int:id_jedi>", methods=["GET"])
def get_jedi(id_jedi):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM jedi WHERE id_jedi = %s", (id_jedi,))
    jedi = cursor.fetchone()
    cursor.close()
    conn.close()
    if jedi:
        return jsonify(jedi)
    return jsonify({"error": "Jedi no encontrado"}), 404

@app.route("/jedis", methods=["POST"])
def create_jedi():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO jedi (nombre_jedi, email_jedi) VALUES (%s, %s)", 
                   (data["nombre_jedi"], data["email_jedi"]))
    conn.commit()
    jedi_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"id_jedi": jedi_id, "message": "Jedi creado"})

@app.route("/jedis/<int:id_jedi>", methods=["PUT"])
def update_jedi(id_jedi):
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE jedi SET nombre_jedi=%s, email_jedi=%s WHERE id_jedi=%s",
                   (data["nombre_jedi"], data["email_jedi"], id_jedi))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Jedi actualizado"})

@app.route("/jedis/<int:id_jedi>", methods=["DELETE"])
def delete_jedi(id_jedi):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jedi WHERE id_jedi=%s", (id_jedi,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Jedi eliminado"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
