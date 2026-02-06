import os, uuid, time, stripe, platform, json
from flask import Flask, request, jsonify, redirect, render_template_string, send_file
from datetime import datetime, timedelta
from database import (
    init_db, create_license, get_license_by_link,
    get_license_by_session, set_active_device
)

app = Flask(__name__, static_url_path='/static', static_folder='static')
init_db()

# ===================== CONFIG =====================
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"
stripe.api_key = STRIPE_SECRET_KEY

PLANES = {
    "price_1Sv5uXBOA5mT4t0PtV7RaYCa": [15.00, 10, "Plan 10 Días"],
    "price_1Sv69jBOA5mT4t0PUA7yiisS": [25.00, 28, "Plan 28 Días"],
    "price_1Sv6H2BOA5mT4t0PppizlRAK": [0.00, 20, "Prueba Admin ($0.00)"]  # SOLO PARA MAYKEL
}

# ===================== VISOR OFFLINE =====================
VIEWER_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AL CIELO – Navegación Offline</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css">
<style>
body {margin:0;background:#000;color:#fff;font-family:sans-serif;}
#map {height:100vh;}
#status {position:fixed;top:10px;left:10px;background:#111;padding:10px;border-radius:8px;font-size:14px;}
#sync {position:fixed;bottom:20px;right:20px;background:#0056b3;color:white;padding:12px 18px;border-radius:10px;font-weight:bold;cursor:pointer;}
</style>
</head>
<body>

<div id="map"></div>
<div id="status">Modo OFFLINE activo</div>
<div id="sync" onclick="syncNow()">🔄 Mejorar precisión</div>

<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
<script>
let map = L.map('map').setView([21.5, -78.9], 7);
let routeLayer = null;
let tilesDownloaded = false;

// Función para cargar tiles offline dinámicamente
async function loadOfflineRoute(){
    const res = await fetch('/get_route_data');
    if(!res.ok){ alert("Error descargando datos offline"); return; }
    const data = await res.json();
    const bounds = data.bounds;
    const route = data.route;

    L.tileLayer('/static/maps/tiles/{z}/{x}/{y}.png', {maxZoom:16,minZoom:6}).addTo(map);

    if(routeLayer) map.removeLayer(routeLayer);
    routeLayer = L.polyline(route, {color:'#00ff00', weight:5}).addTo(map);

    map.fitBounds(routeLayer.getBounds());
    tilesDownloaded = true;
}

// GPS
navigator.geolocation.watchPosition(
 pos => {
   const latlng = [pos.coords.latitude, pos.coords.longitude];
   if(routeLayer){
     const dest = routeLayer.getLatLngs()[routeLayer.getLatLngs().length-1];
     const dist = map.distance(latlng, [dest.lat, dest.lng]);
     if(dist < 50){
        if(confirm("¿Regresará al punto de partida? Si NO, los mapas se borrarán para ahorrar espacio.")){
           alert("Mapa guardado para regreso");
        } else {
           fetch('/delete_route_data').then(()=>alert("Datos eliminados, espacio liberado"));
        }
     }
   }
   map.setView(latlng, 15);
 },
 err => {document.getElementById("status").innerText = "GPS limitado. Usando última posición conocida.";},
 {enableHighAccuracy:true, maximumAge:60000}
);

// Sincronización opcional
function syncNow(){
  if(!navigator.onLine){
    alert("Encienda datos 20–30 segundos para mejorar precisión.");
    return;
  }
  document.getElementById("status").innerText = "Sincronizando datos recientes…";
  fetch('/get_route_data').then(()=>setTimeout(()=>{document.getElementById("status").innerText = "Actualizado. Puede apagar los datos."},3000));
}

loadOfflineRoute();
</script>
</body>
</html>
"""

# ===================== RUTAS =====================
@app.route("/")
def home():
    html = '<div style="max-width:400px;margin:auto;text-align:center;font-family:sans-serif;background:#000;color:white;padding:40px;border-radius:20px;border:2px solid #0056b3;">'
    html += '<h1>AL CIELO</h1><p>MAY ROGA LLC</p><hr>'
    # Mostrar SOLO planes de pago al público
    for pid, (p, d, n) in PLANES.items():
        if pid != "price_1Sv6H2BOA5mT4t0PppizlRAK":  # no mostrar plan gratis
            html += f'<a href="/checkout/{pid}" style="display:block;background:#0056b3;color:white;padding:18px;margin:15px 0;text-decoration:none;border-radius:12px;font-weight:bold;">{n} - ${p}</a>'
    html += '</div>'
    return html

@app.route("/checkout/<pid>")
def checkout(pid):
    # El plan gratis SOLO para MAYKEL (acceso directo)
    if pid == "price_1Sv6H2BOA5mT4t0PppizlRAK":
        lid = str(uuid.uuid4())[:8]
        create_license(lid, f"ADMIN_{lid}", (datetime.utcnow() + timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"))
        return redirect(f"/activar/{lid}")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"], mode="payment",
        line_items=[{"price": pid, "quantity": 1}],
        success_url=f"{BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=BASE_URL
    )
    return redirect(session.url)

@app.route("/success")
def success():
    time.sleep(5)
    return redirect(f"/link/{request.args.get('session_id')}")

@app.route("/link/<session_id>")
def link_redirect(session_id):
    lid = get_license_by_session(session_id)
    return redirect(f"/activar/{lid}") if lid else ("Confirmando...", 404)

@app.route("/activar/<link_id>", methods=["GET","POST"])
def activar(link_id):
    if request.method=="POST":
        if not request.json.get("legal_ok"):
            return jsonify({"error":"Consentimiento requerido"}),403
        device_id = request.json.get("device_id")
        try:
            memoria = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024**3)
        except:
            memoria = 1
        if memoria < 0.5:
            return jsonify({"error":"Memoria insuficiente para navegación offline"}),403
        set_active_device(link_id, device_id)
        return jsonify({"status":"OK", "map_url": f"/viewer/{link_id}"})
    return render_template_string(open("index.html").read())

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "DENEGADO", 403
    return render_template_string(VIEWER_HTML)

# ===================== GENERACIÓN AUTOMÁTICA DE RUTA =====================
ROUTE_FILE = "static/route.json"
@app.route("/get_route_data")
def get_route_data():
    if os.path.exists(ROUTE_FILE):
        with open(ROUTE_FILE) as f:
            data = json.load(f)
    else:
        data = {"bounds":[[21, -79],[22, -78]], "route":[[21.5,-78.9],[21.6,-78.8],[21.7,-78.7]]}
        os.makedirs("static", exist_ok=True)
        with open(ROUTE_FILE,"w") as f: json.dump(data,f)
    return jsonify(data)

@app.route("/delete_route_data")
def delete_route_data():
    try:
        if os.path.exists(ROUTE_FILE): os.remove(ROUTE_FILE)
        return "Datos eliminados"
    except:
        return "Error al borrar",500

# ===================== CABECERAS DE SEGURIDAD =====================
@app.after_request
def add_security_headers(resp):
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp

if __name__=="__main__":
    app.run(host="0.0.0.0", port=10000)
