import os
from pathlib import Path
import requests

# ================= CONFIG =================
MAPS_DIR = Path("static/maps")
MAP_FILE = MAPS_DIR / "cuba_full.mbtiles"
MAP_URL = "https://download.geofabrik.de/central-america/cuba-latest.osm.pbf"  # Fuente de datos OSM

# ================= CREAR CARPETA =================
MAPS_DIR.mkdir(parents=True, exist_ok=True)
print(f"✅ Carpeta {MAPS_DIR} creada o ya existe.")

# ================= DESCARGA DEL ARCHIVO =================
if not MAP_FILE.exists():
    print("⬇️ Descargando archivo de mapas...")
    
    # Descarga del PBF
    pbf_file = MAPS_DIR / "cuba-latest.osm.pbf"
    with requests.get(MAP_URL, stream=True) as r:
        r.raise_for_status()
        with open(pbf_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    print(f"✅ Archivo PBF descargado en {pbf_file}")

    # ================= CONVERTIR A MBTILES =================
    print("⚙️ Convirtiendo a MBTiles...")
    os.system(f"osmtogo {pbf_file} --output={MAP_FILE}")

    # ================= LIMPIEZA =================
    pbf_file.unlink()
    print(f"✅ Conversión completada. Archivo listo en {MAP_FILE}")

else:
    print(f"✅ Archivo {MAP_FILE} ya existe, no es necesario descargar.")

# ================= VERIFICAR ACCESIBILIDAD =================
if MAP_FILE.exists() and MAP_FILE.stat().st_size > 0:
    print(f"✅ {MAP_FILE} listo y accesible desde Flask en /static/maps/")
else:
    print("❌ Error: el archivo MBTiles no se creó correctamente.")
