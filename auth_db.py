import os, sqlite3, json, hashlib, hmac, secrets
from pathlib import Path

DB_PATH = os.environ.get("APP_DB_PATH", "data/base.db")  # usa la misma BD para todo

def get_conn():
    Path(os.path.dirname(DB_PATH) or ".").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def run_script(path_sql: str):
    with get_conn() as con, open(path_sql, "r", encoding="utf-8") as f:
        con.executescript(f.read())

# -------- Password hashing PBKDF2-SHA256 --------
def hash_password(password: str, salt: bytes = None, iterations: int = 130_000) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"

def verify_password(password: str, stored: str) -> bool:
    algo, it_s, salt_hex, dk_hex = stored.split("$")
    assert algo == "pbkdf2_sha256"
    salt = bytes.fromhex(salt_hex)
    iterations = int(it_s)
    new_dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()
    return hmac.compare_digest(new_dk, dk_hex)

# -------- Init + seed --------
def init_auth(schema_path="schema.sql"):
    if not Path(DB_PATH).exists():
        Path(DB_PATH).touch()
    run_script(schema_path)
    seed_roles_and_admin()

def seed_roles_and_admin():
    with get_conn() as con:
        con.execute("INSERT OR IGNORE INTO roles(name) VALUES ('Supervisor')")
        con.execute("INSERT OR IGNORE INTO roles(name) VALUES ('Analista')")
        # Usuario supervisor por defecto
        u = con.execute("SELECT 1 FROM users WHERE username=?", ("supervisor",)).fetchone()
        if not u:
            pwd = hash_password("Cambiar123!")  # cámbiala luego
            con.execute(
                "INSERT INTO users(username, password_hash, full_name) VALUES(?,?,?)",
                ("supervisor", pwd, "Usuario Supervisor")
            )
            uid = con.execute("SELECT id FROM users WHERE username=?", ("supervisor",)).fetchone()["id"]
            rid = con.execute("SELECT id FROM roles WHERE name='Supervisor'").fetchone()["id"]
            con.execute("INSERT OR IGNORE INTO user_roles(user_id, role_id) VALUES (?,?)", (uid, rid))
        con.commit()

# -------- Users & Roles --------
def get_user(username: str):
    with get_conn() as con:
        return con.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()

def get_user_roles(username: str):
    sql = """
    SELECT r.name FROM roles r
    JOIN user_roles ur ON ur.role_id = r.id
    JOIN users u ON u.id = ur.user_id
    WHERE u.username=? AND u.is_active=1
    """
    with get_conn() as con:
        return [r["name"] for r in con.execute(sql, (username,)).fetchall()]

def create_user(username: str, password: str, full_name: str, roles: list[str]):
    with get_conn() as con:
        con.execute("INSERT INTO users(username, password_hash, full_name) VALUES (?,?,?)",
                    (username, hash_password(password), full_name))
        uid = con.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()["id"]
        for role in roles:
            rid = con.execute("SELECT id FROM roles WHERE name=?", (role,)).fetchone()["id"]
            con.execute("INSERT OR IGNORE INTO user_roles(user_id, role_id) VALUES (?,?)", (uid, rid))
        con.commit()

def list_users():
    with get_conn() as con:
        rows = con.execute("SELECT id, username, full_name, is_active FROM users ORDER BY username").fetchall()
        return [dict(r) for r in rows]

def list_roles():
    with get_conn() as con:
        rows = con.execute("SELECT id, name FROM roles ORDER BY name").fetchall()
        return [dict(r) for r in rows]

def set_user_active(user_id: int, active: bool, admin_user: str):
    with get_conn() as con:
        con.execute("UPDATE users SET is_active=? WHERE id=?", (1 if active else 0, user_id))
        u = con.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
        log_event(admin_user, "USER_ACTIVATE" if active else "USER_DEACTIVATE", "users", user_id,
                  details={"username": u["username"]})
        con.commit()

def reset_password(user_id: int, new_password: str, admin_user: str):
    with get_conn() as con:
        h = hash_password(new_password)
        con.execute("UPDATE users SET password_hash=? WHERE id=?", (h, user_id))
        u = con.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
        log_event(admin_user, "USER_RESET_PASSWORD", "users", user_id,
                  details={"username": u["username"]})
        con.commit()

def set_user_roles(user_id: int, role_names: list[str], admin_user: str):
    with get_conn() as con:
        con.execute("DELETE FROM user_roles WHERE user_id=?", (user_id,))
        for rn in role_names:
            rid = con.execute("SELECT id FROM roles WHERE name=?", (rn,)).fetchone()["id"]
            con.execute("INSERT INTO user_roles(user_id, role_id) VALUES (?,?)", (user_id, rid))
        u = con.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
        log_event(admin_user, "USER_SET_ROLES", "users", user_id,
                  details={"username": u["username"], "roles": role_names})
        con.commit()

# -------- Audit Log --------
def log_event(username: str, action: str, entity: str, record_id: int | None,
              reason: str = "", details: dict | None = None):
    with get_conn() as con:
        con.execute(
            "INSERT INTO audit_log(username, action, entity, record_id, reason, details) VALUES (?,?,?,?,?,?)",
            (username, action, entity, record_id, reason, json.dumps(details or {}, ensure_ascii=False))
        )
        con.commit()

def obtener_logs(filtro_user: str | None = None, action: str | None = None, limit: int = 500):
    sql = "SELECT * FROM audit_log WHERE 1=1"
    params = []
    if filtro_user:
        sql += " AND username LIKE ?"; params.append(f"%{filtro_user}%")
    if action:
        sql += " AND action=?"; params.append(action)
    sql += " ORDER BY ts DESC LIMIT ?"; params.append(limit)
    with get_conn() as con:
        return [dict(r) for r in con.execute(sql, params)]