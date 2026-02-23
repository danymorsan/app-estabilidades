# db.py
import os
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = os.environ.get("APP_DB_PATH", "estabilidades.db")

def get_conn():
    Path(os.path.dirname(DB_PATH) or ".").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ----------------- helpers de introspección -----------------
def _table_exists(con, name: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

def _has_column(con, table: str, col: str) -> bool:
    cols = [r[1] for r in con.execute(f"PRAGMA table_info({table});").fetchall()]
    return col in cols

def _resolve_estudios_columns(con):
    """
    Devuelve un dict con los nombres de columnas reales para:
    condicion, material, tiempo_max, created_at, created_by, updated_at, updated_by,
    is_deleted, deleted_at, deleted_by, delete_reason.
    Si no existen, mapea a None y se manejan en consultas con NULL/alias.
    """
    m = {}
    # condicion
    if _has_column(con, "estudios", "condicion"):
        m["condicion"] = "condicion"
    elif _has_column(con, "estudios", "condicion_almacenamiento"):
        m["condicion"] = "condicion_almacenamiento"
    else:
        m["condicion"] = None

    # material
    if _has_column(con, "estudios", "material"):
        m["material"] = "material"
    elif _has_column(con, "estudios", "material_envase"):
        m["material"] = "material_envase"
    else:
        m["material"] = None

    # tiempo_max
    if _has_column(con, "estudios", "tiempo_max"):
        m["tiempo_max"] = "tiempo_max"
    elif _has_column(con, "estudios", "tiempo_max_meses"):
        m["tiempo_max"] = "tiempo_max_meses"
    else:
        m["tiempo_max"] = None

    # auditoría "nueva"
    m["created_at"]   = "created_at"   if _has_column(con, "estudios", "created_at")   else ("fecha_creacion" if _has_column(con, "estudios", "fecha_creacion") else None)
    m["created_by"]   = "created_by"   if _has_column(con, "estudios", "created_by")   else None
    m["updated_at"]   = "updated_at"   if _has_column(con, "estudios", "updated_at")   else None
    m["updated_by"]   = "updated_by"   if _has_column(con, "estudios", "updated_by")   else None
    m["is_deleted"]   = "is_deleted"   if _has_column(con, "estudios", "is_deleted")   else None
    m["deleted_at"]   = "deleted_at"   if _has_column(con, "estudios", "deleted_at")   else None
    m["deleted_by"]   = "deleted_by"   if _has_column(con, "estudios", "deleted_by")   else None
    m["delete_reason"]= "delete_reason"if _has_column(con, "estudios", "delete_reason")else None

    return m

def _resolve_puntos_table(con):
    """
    Devuelve ('puntos', required_cols) o ('puntos_muestreo', required_cols)
    """
    if _table_exists(con, "puntos"):
        return "puntos", ["id", "estudio_id", "mes"]
    if _table_exists(con, "puntos_muestreo"):
        return "puntos_muestreo", ["id", "estudio_id", "mes"]
    return None, []

# ------------------------------------------------------------
# Insertar estudio + puntos (respeta nombres reales)
# ------------------------------------------------------------
def insertar_estudio(datos: dict, meses: list[int], username: str) -> int:
    with get_conn() as con:
        cols = _resolve_estudios_columns(con)
        # construir lista de columnas reales para INSERT
        insert_cols = [
            "tipo_analisis", "cliente", "protocolo", "tipo_estudio", "producto", "lote",
            cols["condicion"] or "condicion",  # si no existe se intentará crear -> por eso mejor alias fijo
            "cabina",
            cols["material"] or "material",
            "fecha_ingreso",
            cols["tiempo_max"] or "tiempo_max",
        ]
        values = [
            datos["tipo_analisis"], datos["cliente"], datos["protocolo"], datos["tipo_estudio"],
            datos["producto"], datos["lote"],
            datos["condicion"], datos["cabina"], datos["material"],
            datos["fecha_ingreso"], int(datos["tiempo_max"])
        ]

        # si existe created_by, lo incluimos
        if cols["created_by"]:
            insert_cols.append("created_by")
            values.append(username)

        # construir SQL respetando que algunas columnas podrían no existir:
        # filtramos solo las columnas que realmente existen en la tabla
        real_cols = [c for c in insert_cols if _has_column(con, "estudios", c)]
        real_vals = [v for c, v in zip(insert_cols, values) if _has_column(con, "estudios", c)]

        if not real_cols:
            raise RuntimeError("La tabla 'estudios' no tiene columnas compatibles para INSERT.")

        placeholders = ",".join(["?"] * len(real_cols))
        sql = f"INSERT INTO estudios ({', '.join(real_cols)}) VALUES ({placeholders})"
        cur = con.execute(sql, real_vals)
        estudio_id = cur.lastrowid

        # Insertar puntos en 'puntos' o 'puntos_muestreo'
        puntos_table, _ = _resolve_puntos_table(con)
        if not puntos_table:
            # crear 'puntos' si no existe ninguno (lo mínimo)
            con.execute("CREATE TABLE IF NOT EXISTS puntos (id INTEGER PRIMARY KEY, estudio_id INTEGER, mes INTEGER)")
            puntos_table = "puntos"

        for m in meses:
            con.execute(f"INSERT INTO {puntos_table} (estudio_id, mes) VALUES (?,?)", (estudio_id, int(m)))

        con.commit()
    return estudio_id

# ------------------------------------------------------------
# Consultas (alias a nombres esperados por la app)
# ------------------------------------------------------------
def obtener_estudios(include_deleted: bool = False) -> pd.DataFrame:
    with get_conn() as con:
        cols = _resolve_estudios_columns(con)

        # SELECT con alias a los nombres que espera la app
        # si una columna no existe -> devolvemos NULL como alias
        def sel(colname, alias):
            if colname and _has_column(con, "estudios", colname):
                return f"{colname} AS {alias}"
            return f"NULL AS {alias}"

        parts = [
            "id",
            "tipo_analisis", "cliente", "protocolo", "tipo_estudio", "producto", "lote",
            sel(cols["condicion"], "condicion"),
            "cabina",
            sel(cols["material"], "material"),
            "fecha_ingreso",
            sel(cols["tiempo_max"], "tiempo_max"),

            sel(cols["is_deleted"], "is_deleted"),
            sel(cols["created_at"], "created_at"),
            sel(cols["created_by"], "created_by"),
            sel(cols["updated_at"], "updated_at"),
            sel(cols["updated_by"], "updated_by"),
            sel(cols["deleted_at"], "deleted_at"),
            sel(cols["deleted_by"], "deleted_by"),
            sel(cols["delete_reason"], "delete_reason"),
        ]
        select_sql = ", ".join(parts)

        where_clause = ""
        if cols["is_deleted"] and not include_deleted:
            where_clause = "WHERE COALESCE(is_deleted, 0)=0"



        order_expr = "COALESCE(updated_at, created_at)" if cols["updated_at"] or cols["created_at"] else "id"

        df = pd.read_sql_query(f"""
            SELECT {select_sql}
            FROM estudios
            {where_clause}
            ORDER BY {order_expr} DESC
        """, con)
    return df

def obtener_puntos() -> pd.DataFrame:
    with get_conn() as con:
        table, _ = _resolve_puntos_table(con)
        if not table:
            # no existe ninguna -> devolver DF vacío
            return pd.DataFrame(columns=["id", "estudio_id", "mes"])
        df = pd.read_sql_query(f"""
            SELECT id, estudio_id, mes
            FROM {table}
            ORDER BY estudio_id, mes
        """, con)
    return df

# ------------------------------------------------------------
# Actualización / Eliminación / Restauración
# ------------------------------------------------------------
def actualizar_estudio(estudio_id: int, cambios: dict, username: str):
    if not cambios:
        return
    with get_conn() as con:
        cols = _resolve_estudios_columns(con)

        # mapear nombres "lógicos" a columnas reales
        mapping = {
            "cliente": "cliente",
            "producto": "producto",
            "lote": "lote",
            "condicion": cols["condicion"],
            "material": cols["material"],
            "tiempo_max": cols["tiempo_max"],
        }

        sets = []
        vals = []
        for k, v in cambios.items():
            real_col = mapping.get(k)
            if real_col and _has_column(con, "estudios", real_col):
                sets.append(f"{real_col}=?")
                vals.append(v)

        # si existen updated_at/updated_by -> los seteamos
        if cols["updated_at"] and cols["updated_by"]:
            sets.append("updated_at=datetime('now')")
            sets.append("updated_by=?")
            vals.append(username)

        if not sets:
            return

        sql = f"UPDATE estudios SET {', '.join(sets)} WHERE id=?"
        vals.append(estudio_id)
        con.execute(sql, vals)
        con.commit()

def soft_delete_estudio(estudio_id: int, username: str, reason: str):
    with get_conn() as con:
        cols = _resolve_estudios_columns(con)
        if cols["is_deleted"]:
            # soft delete real
            sets = ["is_deleted=1"]
            if cols["deleted_at"]:
                sets.append("deleted_at=datetime('now')")
            if cols["deleted_by"]:
                sets.append("deleted_by=?")
            if cols["delete_reason"]:
                sets.append("delete_reason=?")

            vals = []
            if cols["deleted_by"]:
                vals.append(username)
            if cols["delete_reason"]:
                vals.append(reason)

            sql = f"UPDATE estudios SET {', '.join(sets)} WHERE id=?"
            vals.append(estudio_id)
            con.execute(sql, vals)
        else:
            # no hay soporte de soft-delete -> eliminación física
            con.execute("DELETE FROM estudios WHERE id=?", (estudio_id,))
        con.commit()

def restore_estudio(estudio_id: int, username: str, reason: str = "Restauración"):
    with get_conn() as con:
        cols = _resolve_estudios_columns(con)
        if cols["is_deleted"]:
            sets = ["is_deleted=0"]
            # limpiar campos de borrado si existen
            if cols["deleted_at"]:
                sets.append("deleted_at=NULL")
            if cols["deleted_by"]:
                sets.append("deleted_by=NULL")
            if cols["delete_reason"]:
                sets.append("delete_reason=NULL")
            # marcar actualización si existen columnas
            if cols["updated_at"]:
                sets.append("updated_at=datetime('now')")
            if cols["updated_by"]:
                sets.append("updated_by=?")

            vals = []
            if cols["updated_by"]:
                vals.append(username)

            sql = f"UPDATE estudios SET {', '.join(sets)} WHERE id=?"
            vals.append(estudio_id)
            con.execute(sql, vals)
            con.commit()
        else:
            # no hay soporte de restauración si no hay soft-delete
            raise ValueError("La tabla 'estudios' no soporta restauración (no existe is_deleted).")

