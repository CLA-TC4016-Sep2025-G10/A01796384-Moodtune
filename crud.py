# pip install mysql-connector-python flask flask-cors requests
import mysql.connector

# Configurar conexión
conn = mysql.connector.connect(
    host="127.0.0.1",  # Docker expone en localhost
    user="root",
    password="contrasena",
    database="testdb",
    port=3306  # Puerto mapeado en Docker
)
cursor = conn.cursor()

# Crear un jedi
def create_jedi(nombre_jedi, email_jedi):
    cursor.execute("INSERT INTO jedi (nombre_jedi, email_jedi) VALUES (%s, %s)", 
                   (nombre_jedi, email_jedi))
    conn.commit()

# Leer todos los jedis
def read_jedis():
    cursor.execute("SELECT * FROM jedi")
    return cursor.fetchall()

# Actualizar un jedi
def update_jedi(id_jedi, nombre_jedi, email_jedi):
    cursor.execute("UPDATE jedi SET nombre_jedi=%s, email_jedi=%s WHERE id_jedi=%s", 
                   (nombre_jedi, email_jedi, id_jedi))
    conn.commit()

# Eliminar un jedi
def delete_jedi(id_jedi):
    cursor.execute("DELETE FROM jedi WHERE id_jedi=%s", (id_jedi,))
    conn.commit()

# Ejemplo de uso
create_jedi("Luke Skywalker", "luke@jedi.com")
create_jedi("Obi-Wan Kenobi", "obiwan@jedi.com")

print("Jedis:", read_jedis())

update_jedi(1, "Luke S.", "lukeskywalker@jedi.com")
#delete_jedi(2)

print("Jedis después de cambios:", read_jedis())

cursor.close()
conn.close()
