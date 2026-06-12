
import os
import shutil
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
import sqlite3

#configuracion

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DB_PATH      = os.path.join(BASE_DIR, "database", "proveedores.db")
UPLOADS_DIR  = os.path.join(BASE_DIR, "uploads")
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
SCHEMA_PATH  = os.path.join(BASE_DIR, "..", "database", "schema.sql")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)

app = FastAPI(title="Gestión de Proveedores", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
#conexion a la bd
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")  
    return conn

def init_db():
    conn = get_db()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
# modelo de datos
class ProveedorManual(BaseModel):
    nit_empresa:    str
    nombre_empresa: str
    pais:           str
    estado_registro: str

    @field_validator("estado_registro")
    @classmethod
    def validar_estado(cls, v):
        if v.upper() not in ("ACTIVO", "INACTIVO"):
            raise ValueError("estado_registro debe ser ACTIVO o INACTIVO")
        return v.upper()
    @field_validator("nit_empresa", "nombre_empresa", "pais")
    @classmethod
    def no_vacio(cls, v):
        if not v or not v.strip():
            raise ValueError("El campo no puede estar vacío")
        return v.strip()
class ProveedorEdicion(BaseModel):
    nombre_empresa:  Optional[str] = None
    estado_registro: Optional[str] = None

    @field_validator("estado_registro")
    @classmethod
    def validar_estado(cls, v):
        if v is not None and v.upper() not in ("ACTIVO", "INACTIVO"):
            raise ValueError("estado_registro debe ser ACTIVO o INACTIVO")
        return v.upper() if v else v

class ProveedorMasivo(BaseModel):
    nit_empresa:     str
    nombre_empresa:  str
    pais:            str
    estado_registro: str
class InsercionMasivaPayload(BaseModel):
    archivo_id: int
    proveedores: List[ProveedorMasivo]

@app.on_event("startup")
def startup():
    init_db()
    print("Base de datos inicializada correctamente.")

def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    if "fecha_registro" in d and d["fecha_registro"]:
        d["fecha_registro"] = str(d["fecha_registro"])
    return d

#frondend
@app.get("/", include_in_schema=False)
def serve_frontend():
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "Frontend no encontrado. Coloca los archivos en /frontend/"}

#endpoints
@app.post("/api/proveedores/manual", status_code=201)
def crear_proveedor_manual(data: ProveedorManual):
    """Registra un proveedor directamente desde el formulario web."""
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO proveedores
               (nit_empresa, nombre_empresa, pais, tipo_carga, estado_registro, fecha_registro)
               VALUES (?, ?, ?, 'MANUAL', ?, datetime('now'))""",
            (data.nit_empresa, data.nombre_empresa, data.pais, data.estado_registro),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM proveedores WHERE nit_empresa = ?", (data.nit_empresa,)
        ).fetchone()
        return {"ok": True, "proveedor": row_to_dict(row)}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"El NIT '{data.nit_empresa}' ya existe.")
    finally:
        conn.close()


@app.post("/api/proveedores/upload-archivo", status_code=202)
async def subir_archivo(archivo: UploadFile = File(...)):
    allowed = {".csv", ".xlsx", ".xls"}
    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos CSV o Excel.")

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name   = f"{timestamp}_{archivo.filename}"
    dest_path   = os.path.join(UPLOADS_DIR, safe_name)

    with open(dest_path, "wb") as f:
        shutil.copyfileobj(archivo.file, f)

    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO archivos_pendientes (nombre_archivo, ruta_archivo, estado)
               VALUES (?, ?, 'PENDIENTE')""",
            (safe_name, dest_path),
        )
        conn.commit()
        archivo_id = cur.lastrowid
        return {
            "ok":        True,
            "archivo_id": archivo_id,
            "nombre":    safe_name,
            "estado":    "PENDIENTE",
            "mensaje":   "Archivo recibido. El robot lo procesará en breve.",
        }
    finally:
        conn.close()


@app.get("/api/proveedores")
def listar_proveedores():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM proveedores ORDER BY fecha_registro DESC"
        ).fetchall()
        return {"ok": True, "total": len(rows), "proveedores": [row_to_dict(r) for r in rows]}
    finally:
        conn.close()

@app.put("/api/proveedores/{proveedor_id}")
def editar_proveedor(proveedor_id: int, data: ProveedorEdicion):
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT * FROM proveedores WHERE id = ?", (proveedor_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado.")

        nuevo_nombre = data.nombre_empresa  if data.nombre_empresa  else existing["nombre_empresa"]
        nuevo_estado = data.estado_registro if data.estado_registro else existing["estado_registro"]

        conn.execute(
            "UPDATE proveedores SET nombre_empresa = ?, estado_registro = ? WHERE id = ?",
            (nuevo_nombre, nuevo_estado, proveedor_id),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM proveedores WHERE id = ?", (proveedor_id,)
        ).fetchone()
        return {"ok": True, "proveedor": row_to_dict(updated)}
    finally:
        conn.close()

# endpoints del robot

@app.get("/api/robot/archivo-pendiente")
def obtener_archivo_pendiente():
    conn = get_db()
    try:
        row = conn.execute(
            """SELECT * FROM archivos_pendientes
               WHERE estado = 'PENDIENTE'
               ORDER BY fecha_subida ASC
               LIMIT 1"""
        ).fetchone()
        if not row:
            return {"ok": True, "pendiente": False}
        conn.execute(
            "UPDATE archivos_pendientes SET estado = 'PROCESANDO' WHERE id = ?",
            (row["id"],),
        )
        conn.commit()
        return {"ok": True, "pendiente": True, "archivo": row_to_dict(row)}
    finally:
        conn.close()


@app.post("/api/robot/insertar-masivo", status_code=201)
def insertar_masivo(payload: InsercionMasivaPayload):
    conn = get_db()
    try:
        insertados = 0
        errores    = []

        for p in payload.proveedores:
            estado = p.estado_registro.upper() if p.estado_registro else "ACTIVO"
            if estado not in ("ACTIVO", "INACTIVO"):
                estado = "ACTIVO"
            try:
                conn.execute(
                    """INSERT INTO proveedores
                       (nit_empresa, nombre_empresa, pais, tipo_carga, estado_registro, fecha_registro)
                       VALUES (?, ?, ?, 'AUTOMATICO', ?, datetime('now'))""",
                    (p.nit_empresa.strip(), p.nombre_empresa.strip(), p.pais.strip(), estado),
                )
                insertados += 1
            except sqlite3.IntegrityError:
                errores.append(f"NIT duplicado: {p.nit_empresa}")
        conn.execute(
            """UPDATE archivos_pendientes
               SET estado = 'COMPLETADO', fecha_proceso = datetime('now')
               WHERE id = ?""",
            (payload.archivo_id,),
        )
        conn.commit()
        return {
            "ok":        True,
            "insertados": insertados,
            "errores":   errores,
            "mensaje":   f"Proceso completado. {insertados} proveedores insertados.",
        }
    finally:
        conn.close()

@app.get("/api/proveedores/archivo-estado/{archivo_id}")
def estado_archivo(archivo_id: int):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM archivos_pendientes WHERE id = ?", (archivo_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Archivo no encontrado.")
        return {"ok": True, "archivo": row_to_dict(row)}
    finally:
        conn.close()
