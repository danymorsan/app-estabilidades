import sqlite3
from pathlib import Path

DB_PATH = Path("estabilidades.db")

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

# 🔹 CREAMOS TODAS LAS TABLAS

cur.executescript("""
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER,
    role_id INTEGER,
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (role_id) REFERENCES roles(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    action TEXT,
    table_name TEXT,
    record_id INTEGER,
    details TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
""")

con.commit()
con.close()

print("✅ Base de datos creada correctamente.")
