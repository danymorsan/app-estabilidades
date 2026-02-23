# app.py
# --- Fijar rutas absolutas coherentes desde app.py ---
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
os.environ["APP_DB_PATH"] = str(BASE_DIR / "estabilidades.db")  # usar SIEMPRE esta BD
SCHEMA_PATH = str(BASE_DIR / "schema.sql")

import sqlite3

def init_main_db():
    with sqlite3.connect(os.environ["APP_DB_PATH"]) as con:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            con.executescript(f.read())

init_main_db()


import streamlit as st
import pandas as pd
from datetime import date

from catalogs import init_catalogs, list_catalog, add_item, update_item, delete_item, CATALOGS
from db import insertar_estudio, obtener_estudios, obtener_puntos, actualizar_estudio, soft_delete_estudio, restore_estudio
from auth_db import (
    init_auth, get_user, verify_password, get_user_roles, log_event,
    list_users, list_roles, create_user, set_user_active, reset_password, set_user_roles, obtener_logs
)


# ---------------- Configuración ----------------
st.set_page_config(page_title="Cronograma de Estabilidades", page_icon="logo_altea.png", layout="wide")
import os
st.write("DB usada:", os.environ["APP_DB_PATH"])
st.write("Existe archivo:", os.path.exists(os.environ["APP_DB_PATH"]))
st.write("Base de datos en:", os.environ["APP_DB_PATH"])

# ---------------- Inicialización BD ----------------
init_auth(SCHEMA_PATH)     # crea/actualiza users, roles, audit_log (no toca 'estudios')
init_catalogs()            # <--- IMPORTANTE: crea catálogos si faltan

# ---------------- Helpers ----------------
@st.cache_data(ttl=30)
def get_catalog_cached(table):
    return list_catalog(table)

def refresh_catalog(table):
    st.cache_data.clear()

def has_role(r: str) -> bool:
    return r in st.session_state.get("roles", [])

def do_login(username, password):
    u = get_user(username)
    if not u:
        return False
    if verify_password(password, u["password_hash"]):
        st.session_state.user = u["username"]
        st.session_state.roles = get_user_roles(u["username"])
        log_event(u["username"], "LOGIN", "auth", None, details={"ok": True})
        return True
    return False

def password_policy_msg(p: str) -> str | None:
    import re
    if len(p) < 10:
        return "La contraseña debe tener mínimo 10 caracteres."
    clases = sum(bool(re.search(pat, p)) for pat in [r"[A-Z]", r"[a-z]", r"\d", r"[^A-Za-z0-9]"])
    if clases < 3:
        return "Usa al menos 3 de: mayúsculas, minúsculas, números, símbolos."
    return None

# ---------------- Login ----------------
if "user" not in st.session_state:
    st.title("🔐 Iniciar sesión")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        ok = st.form_submit_button("Entrar")
    if ok:
        if do_login(u, p):
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.stop()

# Sidebar / logout
st.sidebar.success(f"Sesión: {st.session_state.user} ({', '.join(st.session_state.get('roles', []))})")
if st.sidebar.button("Cerrar sesión"):
    log_event(st.session_state.user, "LOGOUT", "auth", None, details={"ok": True})
    for k in ("user", "roles"):
        st.session_state.pop(k, None)
    st.rerun()

st.title("Cronograma de Estabilidades")

# ---------------- Tabs según rol ----------------
if has_role("Supervisor"):
    tabs = st.tabs(["📄 Formulario", "📋 Estudios", "📅 Puntos", "🛠️ Listas base (Admin)", "👥 Usuarios (Admin)", "📜 Logs"])
    tab_form, tab_estudios, tab_puntos, tab_admin, tab_users, tab_logs = tabs
else:
    tabs = st.tabs(["📄 Formulario", "📋 Estudios", "📅 Puntos", "📜 Logs"])
    tab_form, tab_estudios, tab_puntos, tab_logs = tabs
    tab_admin = None
    tab_users = None

# ================== FORMULARIO ==================

with tab_form: 
        st.subheader("Registrar nuevo estudio")

        df_tipo_analisis = get_catalog_cached("TbTipoAnalisis") 
        df_clientes = get_catalog_cached("TbClientes") 
        df_tipo_estudio = get_catalog_cached("TbTipoEstudio") 
        df_producto = get_catalog_cached("TbProducto") 
        df_cond_alm = get_catalog_cached("TbCondAlm") 
        df_material = get_catalog_cached("TbMaterialEnvase") 
        tipos_analisis = df_tipo_analisis["nombre"].tolist() 
        clientes = df_clientes["nombre"].tolist() 
        tipos_estudio = df_tipo_estudio["nombre"].tolist() 
        productos = df_producto["nombre"].tolist() 
        condiciones = df_cond_alm["nombre"].tolist() 
        materiales = df_material["nombre"].tolist()

        tipo_analisis = st.selectbox("Tipo de Análisis", tipos_analisis or ["(vacío)"])
        cliente       = st.selectbox("Cliente", clientes or ["(vacío)"])
        tipo_estud    = st.selectbox("Tipo de Estudio", tipos_estudio or ["(vacío)"])
        producto      = st.selectbox("Producto", productos or ["(vacío)"])
        condicion     = st.selectbox("Condición de almacenamiento", condiciones or ["(vacío)"])
        material      = st.selectbox("Material de envase", materiales or ["(vacío)"])

        lote          = st.text_input("Lote")
        cabina        = st.text_input("Cabina")
        protocolo     = st.text_input("Protocolo")
        fecha_ingreso = st.date_input("Fecha de Ingreso", value=date.today())
        tiempo_max    = st.selectbox("Tiempo Máximo (meses)", [3,6,9,12,18,24,36,48])

        meses = st.multiselect("Puntos de Muestreo", list(range(0, tiempo_max+1)))

        can_create = has_role("Supervisor") or has_role("Analista")
        if not can_create:
            st.info("Tu rol no permite crear estudios.")
        else:
            if st.button("💾 Guardar"):
                if not cliente or not producto or not lote:
                    st.warning("Completa Cliente, Producto y Lote.")
                else:
                    datos = {
                        "tipo_analisis": tipo_analisis,
                        "cliente": cliente,
                        "protocolo": protocolo,
                        "tipo_estudio": tipo_estud,
                        "producto": producto,
                        "lote": lote,
                        "condicion": condicion,
                        "cabina": cabina,
                        "material": material,
                        "fecha_ingreso": fecha_ingreso.strftime("%Y-%m-%d"),
                        "tiempo_max": int(tiempo_max)
                    }
                    try:
                        rid = insertar_estudio(datos, meses, st.session_state.user)
                        log_event(
                            st.session_state.user, "INSERT", "estudio", rid,
                            details=datos | {"puntos": meses}
                        )
                        st.success(f"Estudio ID {rid} creado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")


# ================== ESTUDIOS ==================
with tab_estudios:
    st.subheader("📋 Estudios Registrados")
    ver_borrados = st.toggle("Ver eliminados", value=False)
    df_estudios = obtener_estudios(include_deleted=ver_borrados)

    st.dataframe(df_estudios, use_container_width=True)
    st.write("Toggle:", ver_borrados)
    st.write("Total filas:", len(df_estudios))
    


    # Acciones (solo Supervisor)
    if has_role("Supervisor") and not df_estudios.empty:
        st.markdown("### Acciones (Supervisor)")
        col1, col2 = st.columns(2)
        estudio_id = col1.number_input("ID de estudio", min_value=1, step=1)
        accion = col2.selectbox("Acción", ["Editar", "Eliminar", "Restaurar"])

        if accion == "Editar":
            with st.form("edit_form"):
                nuevo_cliente  = st.text_input("Cliente (nuevo)")
                nuevo_producto = st.text_input("Producto (nuevo)")
                nuevo_lote     = st.text_input("Lote (nuevo)")
                nuevo_cond     = st.text_input("Condición (nuevo)")
                nuevo_material = st.text_input("Material envase (nuevo)")
                motivo         = st.text_input("Motivo del cambio (obligatorio)")
                ok = st.form_submit_button("Guardar cambios")
            if ok:
                if not motivo.strip():
                    st.warning("Debes indicar el motivo del cambio.")
                else:
                    cambios = {}
                    if nuevo_cliente:  cambios["cliente"] = nuevo_cliente
                    if nuevo_producto: cambios["producto"] = nuevo_producto
                    if nuevo_lote:     cambios["lote"] = nuevo_lote
                    if nuevo_cond:     cambios["condicion"] = nuevo_cond
                    if nuevo_material: cambios["material"] = nuevo_material

                    if not cambios:
                        st.info("No hay cambios.")
                    else:
                        try:
                            actualizar_estudio(int(estudio_id), cambios, st.session_state.user)
                            log_event(st.session_state.user, "UPDATE", "estudio", int(estudio_id), reason=motivo,
                                      details={"changes": cambios})
                            st.success("Actualizado.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

        elif accion == "Eliminar":
            motivo = st.text_input("Motivo de eliminación")
            if st.button("Confirmar eliminación"):
                if not motivo.strip():
                    st.warning("Motivo requerido.")
                else:
                    try:
                        soft_delete_estudio(int(estudio_id), st.session_state.user, motivo)
                        log_event(st.session_state.user, "DELETE", "estudio", int(estudio_id), reason=motivo)
                        st.success("Eliminado (lógico).")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

        elif accion == "Restaurar":
            motivo = st.text_input("Motivo de restauración")
            if st.button("Confirmar restauración"):
                try:
                    restore_estudio(int(estudio_id), st.session_state.user, motivo or "Restauración")
                    log_event(st.session_state.user, "RESTORE", "estudio", int(estudio_id), reason=motivo or "Restauración")
                    st.success("Restaurado.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

# ================== PUNTOS ==================

with tab_puntos:
    st.subheader("📅 Puntos de Muestreo (detalle)")

    import pandas as pd
    from db import get_conn

    # Leer la vista con detalle
    with get_conn() as con:
        df_puntos = pd.read_sql_query("""
            SELECT 
                id, estudio_id, mes,
                tipo_analisis, cliente, protocolo, tipo_estudio,
                producto, lote, condicion, cabina, material,
                fecha_ingreso, tiempo_max
            FROM v_puntos_detalle
            ORDER BY estudio_id, mes
        """, con)

    # Mostrar tabla enriquecida
    st.dataframe(df_puntos, use_container_width=True, hide_index=True)

    # Gráfico por meses
    if not df_puntos.empty:
        resumen = (
            df_puntos.groupby("mes", as_index=False)
            .size()
            .rename(columns={"size": "conteo"})
        )
        #st.bar_chart(resumen.set_index("mes"))

    # Botón de descarga
    st.download_button(
        "⬇️ Descargar CSV",
        df_puntos.to_csv(index=False).encode("utf-8-sig"),
        file_name="puntos_detalle.csv",
        mime="text/csv"
    )

# ================== LISTAS BASE (ADMIN) ==================
if tab_admin:
    with tab_admin:
        st.subheader("🛠️ Listas base (Admin)")
        st.caption(f"Edita las listas base (guardadas en {os.environ.get('APP_DB_PATH')}).")

        cat = st.selectbox("Selecciona la lista a editar", CATALOGS, format_func=lambda x: x)
        df = get_catalog_cached(cat)

        col_add1, col_add2 = st.columns([3,1])
        with col_add1:
            nuevo = st.text_input("Agregar nuevo valor", key=f"add_{cat}")
        with col_add2:
            if st.button("➕ Agregar", key=f"btn_add_{cat}"):
                add_item(cat, nuevo)
                log_event(st.session_state.user, "INSERT", "catalogo", None, details={"tabla": cat, "valor": nuevo})
                refresh_catalog(cat)
                st.success("Valor agregado")

        st.markdown("### Datos")
        if not df.empty:
            edit_df = st.data_editor(
                df,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                column_config={"id": st.column_config.NumberColumn("id", disabled=True)},
                key=f"editor_{cat}"
            )
            if st.button("💾 Guardar cambios", key=f"save_{cat}"):
                try:
                    orig = df.set_index("id")["nombre"].to_dict()
                    new  = edit_df.set_index("id")["nombre"].to_dict()
                    for _id, new_name in new.items():
                        if _id in orig and orig[_id] != new_name:
                            update_item(cat, int(_id), new_name)
                            log_event(st.session_state.user, "UPDATE", "catalogo", int(_id),
                                      details={"tabla": cat, "before": orig[_id], "after": new_name})
                    deleted_ids = set(orig.keys()) - set(new.keys())
                    for _id in deleted_ids:
                        delete_item(cat, int(_id))
                        log_event(st.session_state.user, "DELETE", "catalogo", int(_id), details={"tabla": cat})
                    refresh_catalog(cat)
                    st.success("Cambios guardados.")
                except Exception as e:
                    st.error(f"Error guardando cambios: {e}")
        else:
            st.info("Esta lista está vacía. Agrega valores arriba.")

# ================== USUARIOS (ADMIN) ==================
if tab_users:
    with tab_users:
        st.subheader("👥 Administración de usuarios")

        with st.expander("➕ Crear usuario", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input("Usuario")
                full_name = st.text_input("Nombre completo")
            with col2:
                pwd1 = st.text_input("Contraseña", type="password")
                pwd2 = st.text_input("Confirmar contraseña", type="password")
                roles_disponibles = [r["name"] for r in list_roles()]
                roles_sel = st.multiselect("Roles", roles_disponibles, default=["Analista"])

            if st.button("Crear usuario"):
                if not new_username or not pwd1 or not pwd2:
                    st.warning("Completa usuario y contraseña.")
                elif pwd1 != pwd2:
                    st.warning("Las contraseñas no coinciden.")
                elif (err := password_policy_msg(pwd1)):
                    st.warning(err)
                else:
                    try:
                        create_user(new_username, pwd1, full_name, roles_sel)
                        log_event(st.session_state.user, "USER_CREATE", "users", None,
                                  details={"username": new_username, "roles": roles_sel})
                        st.success(f"Usuario '{new_username}' creado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo crear el usuario: {e}")

        st.markdown("---")
        usuarios = list_users()
        if not usuarios:
            st.info("No hay usuarios.")
        else:
            dfu = pd.DataFrame(usuarios)
            st.dataframe(dfu, use_container_width=True, hide_index=True)

            st.markdown("### Acciones sobre usuario")
            colA, colB = st.columns([2,1])
            user_id = colA.number_input("ID de usuario", min_value=1, step=1)
            accion = colB.selectbox("Acción", ["Asignar roles", "Resetear contraseña", "Activar", "Desactivar"])

            if accion == "Asignar roles":
                roles_disponibles = [r["name"] for r in list_roles()]
                roles_sel = st.multiselect("Nuevos roles", roles_disponibles)
                if st.button("Aplicar"):
                    try:
                        set_user_roles(int(user_id), roles_sel, st.session_state.user)
                        st.success("Roles actualizados.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

            elif accion == "Resetear contraseña":
                np1 = st.text_input("Nueva contraseña", type="password")
                np2 = st.text_input("Confirmar nueva contraseña", type="password")
                if st.button("Resetear"):
                    if np1 != np2:
                        st.warning("Las contraseñas no coinciden.")
                    elif (err := password_policy_msg(np1)):
                        st.warning(err)
                    else:
                        try:
                            reset_password(int(user_id), np1, st.session_state.user)
                            st.success("Contraseña actualizada.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

            elif accion == "Activar":
                if st.button("Confirmar activación"):
                    try:
                        set_user_active(int(user_id), True, st.session_state.user)
                        st.success("Usuario activado.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

            elif accion == "Desactivar":
                if st.button("Confirmar desactivación"):
                    try:
                        set_user_active(int(user_id), False, st.session_state.user)
                        st.success("Usuario desactivado.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

# ================== LOGS ==================
with tab_logs:
    st.subheader("📜 Audit Log")
    colf1, colf2, colf3 = st.columns([2,1,1])
    f_user = colf1.text_input("Filtrar por usuario")
    f_action = colf2.selectbox("Acción", ["", "LOGIN", "LOGOUT", "INSERT", "UPDATE", "DELETE", "RESTORE",
                                          "USER_CREATE", "USER_SET_ROLES", "USER_RESET_PASSWORD",
                                          "USER_ACTIVATE", "USER_DEACTIVATE"])
    limit = colf3.number_input("Límite", min_value=50, max_value=5000, value=500, step=50)

    logs = obtener_logs(f_user or None, f_action or None, limit=int(limit))
    if logs:
        dfl = pd.DataFrame(logs)
        st.dataframe(dfl, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Descargar CSV",
            dfl.to_csv(index=False).encode("utf-8-sig"),
            file_name="audit_log.csv",
            mime="text/csv"
        )
    else:
        st.info("Sin eventos para los filtros actuales.")
