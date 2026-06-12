
import sys
import time
import argparse
import logging
import requests
import pandas as pd


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [ROBOT]  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("robot-rpa")



parser = argparse.ArgumentParser(description="Robot RPA – Gestión de Proveedores")
parser.add_argument("--url",       default="http://localhost:8000", help="URL base del backend")
parser.add_argument("--intervalo", type=int, default=5, help="Segundos entre cada consulta al backend")
args = parser.parse_args()

API_BASE   = args.url.rstrip("/")
INTERVALO  = args.intervalo

COLUMNAS_REQUERIDAS = {"nit_empresa", "nombre_empresa", "pais", "estado_registro"}


def leer_archivo(ruta: str) -> pd.DataFrame:
    ext = ruta.lower().split(".")[-1]
    log.info(f"📂  Abriendo archivo: {ruta}  (formato: {ext})")
    if ext == "csv":
        df = pd.read_csv(ruta, dtype=str, encoding="utf-8-sig")
    elif ext in ("xlsx", "xls"):
        df = pd.read_excel(ruta, dtype=str)
    else:
        raise ValueError(f"Formato no soportado: {ext}")
    df.columns = [c.strip().lower() for c in df.columns]
    return df



def validar_fila(fila: dict, numero: int) -> tuple[bool, str]:
    for col in COLUMNAS_REQUERIDAS:
        valor = fila.get(col, "")
        if not valor or str(valor).strip().lower() in ("nan", "none", ""):
            return False, f"Fila {numero}: campo '{col}' vacío o inválido."

    estado = str(fila.get("estado_registro", "")).strip().upper()
    if estado not in ("ACTIVO", "INACTIVO"):
        return False, f"Fila {numero}: estado_registro '{estado}' inválido. Debe ser ACTIVO o INACTIVO."

    return True, ""



def ciclo_robot():
    log.info(f"🤖  Robot iniciado. Consultando {API_BASE} cada {INTERVALO}s")
    log.info("    Presiona Ctrl+C para detener.\n")

    while True:
        try:
            resp = requests.get(f"{API_BASE}/api/robot/archivo-pendiente", timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if not data.get("pendiente"):
                log.info("⏳  Sin archivos pendientes. Esperando...")
                time.sleep(INTERVALO)
                continue

            archivo_info = data["archivo"]
            archivo_id   = archivo_info["id"]
            ruta         = archivo_info["ruta_archivo"]
            nombre       = archivo_info["nombre_archivo"]

            log.info(f"📥  Archivo detectado: {nombre}  (id={archivo_id})")
            log.info(f"    Estado actualizado a PROCESANDO en el backend.")

            try:
                df = leer_archivo(ruta)
            except Exception as e:
                log.error(f"❌  No se pudo leer el archivo: {e}")
                time.sleep(INTERVALO)
                continue

            cols_faltantes = COLUMNAS_REQUERIDAS - set(df.columns)
            if cols_faltantes:
                log.error(f"❌  El archivo no tiene las columnas: {cols_faltantes}")
                time.sleep(INTERVALO)
                continue

            log.info(f"📊  {len(df)} filas encontradas en el archivo.")

            proveedores_validos = []
            for idx, row in df.iterrows():
                fila = row.to_dict()
                es_valida, mensaje = validar_fila(fila, idx + 2)  
                if es_valida:
                    proveedores_validos.append({
                        "nit_empresa":     str(fila["nit_empresa"]).strip(),
                        "nombre_empresa":  str(fila["nombre_empresa"]).strip(),
                        "pais":            str(fila["pais"]).strip(),
                        "estado_registro": str(fila["estado_registro"]).strip().upper(),
                    })
                    log.info(f"   ✔  Fila {idx+2}: {fila['nombre_empresa']} ({fila['nit_empresa']})")
                else:
                    log.warning(f"   ✘  {mensaje}")

            log.info(f"✅  Validación completada: {len(proveedores_validos)} filas válidas.")

            if not proveedores_validos:
                log.warning("⚠️   Sin datos válidos para insertar.")
                time.sleep(INTERVALO)
                continue

            log.info("🚀  Enviando datos al backend (POST /api/robot/insertar-masivo)...")
            payload = {
                "archivo_id":  archivo_id,
                "proveedores": proveedores_validos,
            }
            resp_insert = requests.post(
                f"{API_BASE}/api/robot/insertar-masivo",
                json=payload,
                timeout=30,
            )
            resp_insert.raise_for_status()
            resultado = resp_insert.json()

            log.info(f"🎉  Proceso completado!")
            log.info(f"    ✔ Insertados:  {resultado.get('insertados', 0)}")
            if resultado.get("errores"):
                for e in resultado["errores"]:
                    log.warning(f"    ⚠  {e}")
            log.info(f"    Estado del archivo → COMPLETADO\n")

        except requests.exceptions.ConnectionError:
            log.error(f"🔌  No se puede conectar al backend en {API_BASE}. ¿Está corriendo?")
        except requests.exceptions.HTTPError as e:
            log.error(f"🔴  Error HTTP: {e}")
        except KeyboardInterrupt:
            log.info("\n⛔  Robot detenido por el usuario.")
            sys.exit(0)
        except Exception as e:
            log.error(f"💥  Error inesperado: {e}", exc_info=True)

        time.sleep(INTERVALO)


if __name__ == "__main__":
    ciclo_robot()
