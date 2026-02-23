# catalogs.py
import os, sqlite3, pandas as pd
from pathlib import Path

DB_PATH = os.environ.get("APP_DB_PATH", str(Path(__file__).resolve().parent / "estabilidades.db"))
Path(os.path.dirname(DB_PATH) or ".").mkdir(parents=True, exist_ok=True)

CATALOGS = [
    "TbTipoAnalisis",
    "TbClientes",
    "TbTipoEstudio",
    "TbProducto",
    "TbCondAlm",
    "TbMaterialEnvase",
]

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_catalogs():
    with get_conn() as con:
        for t in CATALOGS:
            con.execute(f"CREATE TABLE IF NOT EXISTS {t} (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE NOT NULL)")
        con.commit()

def list_catalog(table: str) -> pd.DataFrame:
    with get_conn() as con:
        return pd.read_sql_query(f"SELECT id, nombre FROM {table} ORDER BY nombre", con)

def add_item(table: str, nombre: str):
    if not nombre or not nombre.strip():
        return
    with get_conn() as con:
        con.execute(f"INSERT OR IGNORE INTO {table}(nombre) VALUES (?)", (nombre.strip(),))
        con.commit()

def update_item(table: str, item_id: int, new_name: str):
    with get_conn() as con:
        con.execute(f"UPDATE {table} SET nombre=? WHERE id=?", (new_name.strip(), item_id))
        con.commit()

def delete_item(table: str, item_id: int):
    with get_conn() as con:
        con.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
        con.commit()
