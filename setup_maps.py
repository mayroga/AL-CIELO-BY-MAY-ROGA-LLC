#!/usr/bin/env python3
import os
from pathlib import Path
import urllib.request
import stat

# ================= CONFIG =================
MAPS_DIR = Path("static/maps")
MAP_FILE = MAPS_DIR / "cuba_full.mbtiles"

# URL de descarga del .mbtiles (ajustar según tu fuente)
MBTILES_URL = "https://tu-servidor.com/cuba_full.mbtiles"

# ================== FUNCIONES ==================
def ensure_maps_dir():
    if not MAPS_DIR.exists():
        MAPS_DIR.mkdir(parents=True, exist_ok=True)
        print(f"✅ Carpeta {MAPS_DIR} creada.")
    else:
        print(f"✅ Carpeta {MAPS_DIR} ya existe.")

def download_mbtiles():
    if MAP_FILE.exists():
        print(f"✅ Archivo {MAP_FILE} ya existe, no se descarga.")
        return
    print(f"⬇️ Descargando {MAP_FILE.name} ...")
    urllib.request.urlretrieve(MBTILES_URL, MAP_FILE)
    print(f"✅ Descarga completada: {MAP_FILE}")

def set_permissions():
    # Lectura para todos, escritura solo propietario
    MAP_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
    print(f"🔒 Permisos ajustados para {MAP_FILE}")

def main():
    ensure_maps_dir()
    download_mbtiles()
    set_permissions()
    print(f"🎯 {MAP_FILE} listo y accesible desde Flask en /static/maps/")

if __name__ == "__main__":
    main()
