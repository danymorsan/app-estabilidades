# migrate_columns.py
import os, sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("APP_DB_PATH", str(BASE_DIR / "estabilidades.db"))

def add_column_if_missing(table, col_name, col_type="TEXT"):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    # comprobar que la tabla existe
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
        print(f"❌ La tabla {table} no existe en {DB_PATH}")
        con.close()
        return False
    cols = [r["name"] for r in con.execute(f"PRAGMA table_info({table});").fetchall()]
    if col_name not in cols:
        print(f"➕ Agregando columna {col_name} a {table} ...")
        con.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
        con.commit()
    else:
        print(f"✔ {table}.{col_name} ya existe.")
    con.close()
    return True

def copy_if_exists(dst_col, src_col):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cols = [r["name"] for r in con.execute("PRAGMA table_info(estudios);").fetchall()]
    if src_col in cols and dst_col in cols:
        print(f"↪ Copiando {src_col} → {dst_col} (solo si destino está vacío)...")
        con.execute(f"UPDATE estudios SET {dst_col} = {src_col} WHERE {dst_col} IS NULL OR {dst_col} = ''")
        con.commit()
    con.close()

if __name__ == "__main__":
    print("Usando BD:", DB_PATH)

    # Crea columnas nuevas y copia desde las viejas si existieran
    if add_column_if_missing("estudios", "condicion", "TEXT"):
        copy_if_exists("condicion", "cond_alm")

    if add_column_if_missing("estudios", "material", "TEXT"):
        copy_if_exists("material", "material_envase")

    print("✔ Migración terminada.")