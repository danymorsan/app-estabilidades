CREATE TABLE IF NOT EXISTS estudios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_analisis TEXT NOT NULL,
    cliente TEXT,
    protocolo TEXT,
    tipo_estudio TEXT,
    producto TEXT,
    lote TEXT,
    condicion TEXT,
    cabina TEXT,
    material TEXT,
    fecha_ingreso DATE NOT NULL,
    tiempo_max INTEGER NOT NULL,

    is_deleted INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    created_by TEXT,
    updated_at TEXT,
    updated_by TEXT,
    deleted_at TEXT,
    deleted_by TEXT,
    delete_reason TEXT
);

CREATE TABLE IF NOT EXISTS puntos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estudio_id INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    FOREIGN KEY (estudio_id) REFERENCES estudios(id)
);
-- ========================
-- TABLAS DE AUTENTICACIÓN
-- ========================

CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
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
    entity TEXT,
    record_id INTEGER,
    reason TEXT,
    details TEXT,
    ts TEXT DEFAULT (datetime('now'))
);
-- ========================
-- VISTA DETALLE PUNTOS
-- ========================

DROP VIEW IF EXISTS v_puntos_detalle;

CREATE VIEW v_puntos_detalle AS
SELECT 
    p.id,
    p.estudio_id,
    p.mes,
    e.tipo_analisis,
    e.cliente,
    e.protocolo,
    e.tipo_estudio,
    e.producto,
    e.lote,
    e.condicion,
    e.cabina,
    e.material,
    e.fecha_ingreso,
    e.tiempo_max,
    DATE(e.fecha_ingreso, '+' || e.tiempo_max || ' months') AS fecha_vencimiento,
    -- Fecha por punto de muestreo
    DATE(e.fecha_ingreso, '+' || p.mes || ' months') AS fecha_max_muestreo
FROM puntos p
JOIN estudios e ON p.estudio_id = e.id
WHERE e.is_deleted = 0;
