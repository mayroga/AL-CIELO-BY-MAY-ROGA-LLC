import sqlite3
import os
from pathlib import Path

def extract_mbtiles(mbtiles_path, output_dir):
    if not os.path.exists(mbtiles_path):
        print(f"Error: No se encuentra {mbtiles_path}")
        return

    conn = sqlite3.connect(mbtiles_path)
    cur = conn.cursor()
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Obtenemos los tiles de la base de datos
    cur.execute("SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles")
    
    print("Extrayendo mapas... esto puede tardar unos minutos.")
    count = 0
    for row in cur:
        z, x, y, data = row
        # MBTiles usa un esquema de filas invertido (TMS), lo corregimos para OpenStreetMap estándar
        y_osm = (1 << z) - 1 - y
        
        tile_dir = os.path.join(output_dir, str(z), str(x))
        os.makedirs(tile_dir, exist_ok=True)
        
        tile_path = os.path.join(tile_dir, f"{y_osm}.png")
        with open(tile_path, "wb") as f:
            f.write(data)
        count += 1
    
    conn.close()
    print(f"✅ Éxito: {count} imágenes extraídas en {output_dir}")

if __name__ == "__main__":
    extract_mbtiles("static/maps/cuba_full.mbtiles", "static/maps/cuba_tiles")
