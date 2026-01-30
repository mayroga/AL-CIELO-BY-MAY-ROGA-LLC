import sqlite3
import os

def extract():
    mbtiles = "static/maps/cuba_full.mbtiles"
    out_dir = "static/maps/cuba_tiles"
    
    if not os.path.exists(mbtiles):
        print("❌ ERROR: No veo el archivo cuba_full.mbtiles en static/maps/")
        return

    conn = sqlite3.connect(mbtiles)
    cursor = conn.cursor()

    # Detectar nombre de tabla correcto
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    target_table = "tiles" if "tiles" in tables else "map" if "map" in tables else None

    if not target_table:
        print(f"❌ ERROR: El archivo mbtiles no es válido. Tablas encontradas: {tables}")
        return

    print(f"✅ Extrayendo desde la tabla: {target_table}...")

    # Consulta flexible
    query = f"SELECT zoom_level, tile_column, tile_row, tile_data FROM {target_table}"
    cursor.execute(query)

    count = 0
    for z, x, y, data in cursor:
        # Corrección de eje Y (TMS a OSM)
        y_osm = (1 << z) - 1 - y
        
        path = os.path.join(out_dir, str(z), str(x))
        os.makedirs(path, exist_ok=True)
        
        with open(os.path.join(path, f"{y_osm}.png"), "wb") as f:
            f.write(data)
        count += 1
        if count % 500 == 0: print(f"Procesadas {count} imágenes...")

    conn.close()
    print(f"✅ ÉXITO TOTAL: {count} imágenes listas para uso offline.")

if __name__ == "__main__":
    extract()
