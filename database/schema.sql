
CREATE TABLE IF NOT EXISTS proveedores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nit_empresa     TEXT    NOT NULL UNIQUE,
    nombre_empresa  TEXT    NOT NULL,
    pais            TEXT    NOT NULL,
    tipo_carga      TEXT    NOT NULL CHECK (tipo_carga IN ('MANUAL', 'AUTOMATICO')),
    estado_registro TEXT    NOT NULL CHECK (estado_registro IN ('ACTIVO', 'INACTIVO')),
    fecha_registro  DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS archivos_pendientes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_archivo  TEXT    NOT NULL,
    ruta_archivo    TEXT    NOT NULL,
    estado          TEXT    NOT NULL DEFAULT 'PENDIENTE'
                    CHECK (estado IN ('PENDIENTE', 'PROCESANDO', 'COMPLETADO', 'ERROR')),
    fecha_subida    DATETIME NOT NULL DEFAULT (datetime('now')),
    fecha_proceso   DATETIME
);
