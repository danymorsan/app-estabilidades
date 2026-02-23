import sqlite3

# 1. Crear conexión (si no existe el archivo, lo crea)
conn = sqlite3.connect("estabilidades.db")

# 2. Crear cursor (permite ejecutar comandos SQL)
cursor = conn.cursor()

# 3. Crear tabla estudios
cursor.execute("""
CREATE TABLE IF NOT EXISTS estudios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_analisis TEXT NOT NULL,
    cliente TEXT,
    protocolo TEXT,
    tipo_estudio TEXT,
    producto TEXT,
    lote TEXT,
    condicion_almacenamiento TEXT,
    cabina TEXT,
    material_envase TEXT,
    fecha_ingreso DATE NOT NULL,
    tiempo_max_meses INTEGER NOT NULL,
    punto_de:muestreo INTEGER NOT NULL
);
""")

# 4. Crear tabla puntos_muestreo
cursor.execute("""
CREATE TABLE IF NOT EXISTS puntos_muestreo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estudio_id INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    fecha_programada DATE,
    fecha_finalizacion DATE,
    FOREIGN KEY (estudio_id) REFERENCES estudios(id)
);
""")

# 5. Guardar cambios
conn.commit()

# 6. Cerrar conexión
conn.close()

print("Base de datos creada correctamente.")

import sqlite3
import pandas as pd

conn = sqlite3.connect("estabilidades.db")

df = pd.read_sql_query("SELECT * FROM estudios", conn)

print(df)

conn.close()

