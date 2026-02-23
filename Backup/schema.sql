-----------------------------------------------------------------------
-- ROLES Y USUARIOS
-----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY,
  username      TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  full_name     TEXT,
  is_active     INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS roles (
  id   INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL   -- 'Supervisor' | 'Analista'
);

CREATE TABLE IF NOT EXISTS user_roles (
  user_id INTEGER NOT NULL,
  role_id INTEGER NOT NULL,
  PRIMARY KEY (user_id, role_id),
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (role_id) REFERENCES roles(id)
);

-----------------------------------------------------------------------
-- LOG DE AUDITORÍA (append-only)
-----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit_log (
  id        INTEGER PRIMARY KEY,
  ts        TEXT DEFAULT (datetime('now')),
  username  TEXT,           -- usuario que hizo la acción
  action    TEXT,           -- LOGIN, INSERT, UPDATE, DELETE, RESTORE, USER_CREATE...
  entity    TEXT,           -- 'estudio', 'usuarios', 'catalogo', etc.
  record_id INTEGER,
  reason    TEXT,           -- motivo si aplica
  details   TEXT            -- JSON con before/after u otros detalles
);

-----------------------------------------------------------------------
-- ROLES POR DEFECTO
-----------------------------------------------------------------------

INSERT OR IGNORE INTO roles(name) VALUES ('Supervisor');
INSERT OR IGNORE INTO roles(name) VALUES ('Analista');