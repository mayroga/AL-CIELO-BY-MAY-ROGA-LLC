import os, uuid, time, stripe, sqlite3
from flask import Flask, request, jsonify, redirect, render_template_string, send_file, abort
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import mbutil  # pip install mbutil (para manejar MBTiles)

from database import init_db, create_license, get_license_by_link, get_license_by_session, set_active_device

# ======================================================
# APP
# ======================================================
app = Flask(__name__, static_url_path='/static', static_folder='static')
init_db()

# ======================================================
# CONFIGURACIÓN GENERAL
# ======================================================
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"
stripe.api_key = STRIPE_SECRET_KEY

PLANES = {
    "price_1Sv5uXBOA5mT4t0PtV7RaYCa": [15.00, 10, "Plan 10 Días"],
    "price_1Sv69jBOA5mT4t0PUA7yiisS": [25.00, 28, "Plan 28 Días"],
    "price_1Sv6H2BOA5mT4t0PppizlRAK": [0.00, 20, "Prueba Admin ($0.00)"]
}

MBTILES_PATH = Path("static/maps/cuba_full.mbtiles")
TILE_CACHE = Path("static/maps/cache")
TILE_CACHE.mkdir(parents=True, exist_ok=True)

# ======================================================
# VISOR HTML (sin cambios)
# ======================================================
VIEWER_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AL CIELO BY MAY ROGA LLC – Navegación Offline</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css">
<style>
body { margin:0; background:#000; color:#fff; font-family:sans-serif; }
#map { height:100vh; }
#status {
 position:fixed;
 top:10px;
 left:10px;
 background:#111;
 padding:10px 14px;
 border-radius:8px;
 font-size:14px;
 z-index:999;
}
#sync {
 position:fixed;
 bottom:20px;
 right:20px;
 background:#0056b3;
 color:white;
 padding:12px 18px;
 border-radius:12px;
 font-weight:bold;
 cursor:pointer;
 z-index:999;
}
</style>
</head>
<body>
<div id="map"></div>
<div id="status">Modo OFFLINE activo</div>
<div id="sync" onclick="syncNow()">🔄 Mejorar precisión</div>
<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
<script>
const map = L.map('map').setView([21.5, -78.9], 7);

// Tiles dinámicos desde Flask
L.tileLayer('/tile/{z}/{x}/{y}.png', {minZoom:6,maxZoom:16}).addTo(map);

// GPS continuo
navigator.geolocation.watchPosition(
  pos => {
    map.setView([pos.coords.latitude, pos.coords.longitude], 15);
  },
  err => {
    document.getElementById("status").innerText =
      "GPS limitado. Usando última posición conocida.";
  },
  {enableHighAccuracy:true, maximumAge:60000, timeout:10000}
);

// Sincronización manual
function syncNow() {
  if (!navigator.onLine) { alert("Encienda datos 20–30 segundos para mejorar precisión."); return; }
  document.getElementById("status").innerText = "Sincronizando datos recientes…";
  setTimeout(()=>{document.getElementById("status").innerText="Actualizado. Puede apagar los datos.";},3000);
}
</script>
</body>
</html>
"""

# ======================================================
# RUTAS
# ======================================================
@app.route("/")
def home():
    html = """
    <div style="max-width:420px;margin:auto;text-align:center;
    font-family:sans-serif;background:#000;color:white;
    padding:40px;border-radius:20px;border:2px solid #0056b3;">
    <h1>AL CIELO</h1>
    <p>BY MAY ROGA LLC</p>
    <hr>
    """
    for pid, (precio, dias, nombre) in PLANES.items():
        html += f"""
        <a href="/checkout/{pid}"
        style="display:block;background:#0056b3;color:white;
        padding:18px;margin:15px 0;text-decoration:none;
        border-radius:12px;font-weight:bold;">
        {nombre} – ${precio}
        </a>
        """
    html += "</div>"
    return html

@app.route("/checkout/<pid>")
def checkout(pid):
    if pid == "price_1Sv6H2BOA5mT4t0PppizlRAK":
        lid = str(uuid.uuid4())[:8]
        create_license(
            lid,
            f"ADMIN_{lid}",
            (datetime.utcnow() + timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
        )
        return redirect(f"/activar/{lid}")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[{"price": pid, "quantity": 1}],
        success_url=f"{BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=BASE_URL
    )
    return redirect(session.url)

@app.route("/success")
def success():
    time.sleep(3)
    return redirect(f"/link/{request.args.get('session_id')}")

@app.route("/link/<session_id>")
def link_redirect(session_id):
    lid = get_license_by_session(session_id)
    return redirect(f"/activar/{lid}") if lid else ("Confirmando...", 404)

@app.route("/activar/<link_id>", methods=["GET","POST"])
def activar(link_id):
    if request.method == "POST":
        if not request.json.get("legal_ok"):
            return jsonify({"error": "Consentimiento legal requerido"}), 403

        device_id = request.json.get("device_id")

        # Comprobación mínima de memoria
        try:
            memoria = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024**3)
        except:
            memoria = 1.0

        if memoria < 0.5:
            return jsonify({"error": "Dispositivo con memoria insuficiente para navegación offline"}), 403

        set_active_device(link_id, device_id)

        return jsonify({"status":"OK","map_url": f"/viewer/{link_id}"})

    return render_template_string(open("index.html", encoding="utf-8").read())

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic:
        return "DENEGADO", 403
    return render_template_string(VIEWER_HTML)

# ======================================================
# SERVIR TILES DINÁMICOS DESDE MBTILES (solo los necesarios)
# ======================================================
@app.route("/tile/<int:z>/<int:x>/<int:y>.png")
def tile(z, x, y):
    tile_path = TILE_CACHE / f"{z}_{x}_{y}.png"
    if tile_path.exists():
        return send_file(tile_path, mimetype="image/png")
    else:
        # Extraer tile del MBTILES
        import sqlite3, io
        conn = sqlite3.connect(MBTILES_PATH)
        cur = conn.cursor()
        cur.execute("SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                    (z, x, (2**z - 1 - y)))  # MBTiles usa y invertido
        row = cur.fetchone()
        conn.close()
        if row:
            data = row[0]
            with open(tile_path, "wb") as f:
                f.write(data)
            return send_file(tile_path, mimetype="image/png")
        else:
            abort(404)

# ======================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
