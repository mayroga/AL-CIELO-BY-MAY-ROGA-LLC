import os, uuid, time, stripe
from flask import Flask, request, jsonify, redirect, render_template_string
from datetime import datetime, timedelta
from database import init_db, create_license, get_license_by_link, get_license_by_session, set_active_device

app = Flask(__name__, static_url_path='/static', static_folder='static')
init_db()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"
stripe.api_key = STRIPE_SECRET_KEY

PLANES = {
    "price_1Sv5uXBOA5mT4t0PtV7RaYCa": [15.00, 10, "Plan 10 Días"],
    "price_1Sv69jBOA5mT4t0PUA7yiisS": [25.00, 28, "Plan 28 Días"],
    "price_1Sv6H2BOA5mT4t0PppizlRAK": [0.00, 20, "Admin Test"]
}

VIEWER_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <title>AL CIELO - GPS Profesional Cuba</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css" />
    <style>
        body { margin:0; background:#000; font-family: sans-serif; color:white; overflow:hidden; }
        #map { height: 70vh; width: 100%; border-bottom: 4px solid #0056b3; }
        .ui-panel { height: 30vh; background:#111; padding:10px; display:flex; flex-direction:column; gap:5px; position:relative; }
        .speed-box { position: absolute; top: -60px; right: 10px; background: rgba(0,0,0,0.8); border: 2px solid #00ff00; border-radius: 50%; width: 50px; height: 50px; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #00ff00; z-index: 1000; font-size: 12px; text-align: center; }
        .search-row { display: flex; gap: 5px; }
        input { flex:1; padding:10px; border-radius:5px; border:1px solid #333; background:#222; color:white; }
        button { padding:12px; border-radius:5px; border:none; font-weight:bold; cursor:pointer; text-transform:uppercase; }
        .btn-go { background:#0056b3; color:white; }
        .btn-opt { background:#333; color:#ccc; font-size:10px; }
        #instrucciones { color:#00ff00; font-size:14px; text-align:center; font-weight:bold; min-height:1.5em; }
        .car-icon { font-size: 40px !important; filter: drop-shadow(0 0 5px #fff); }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="ui-panel">
        <div class="speed-box"><span id="speed">0</span><br>km/h</div>
        <div id="instrucciones">ESPERANDO ORIGEN Y DESTINO</div>
        <div class="search-row">
            <input id="origin" placeholder="Origen">
            <input id="destination" placeholder="Destino">
        </div>
        <button class="btn-go" onclick="calcularRutas()">BUSCAR OPCIONES DE RUTA</button>
        <div class="search-row">
            <button class="btn-opt" onclick="iniciarGPS()">GPS REAL</button>
            <button class="btn-opt" onclick="borrarRastro()">BORRAR TODO</button>
        </div>
        <div style="font-size:9px; color:#444; text-align:center;">MAY ROGA LLC - AL CIELO v2026</div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    <script>
        var map = L.map('map', { zoomControl: false }).setView([21.5, -79.5], 7);
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

        var carMarker = L.marker([0,0], {
            icon: L.divIcon({ className: 'car-icon', html: '🚗', iconSize: [40, 40], iconAnchor: [20, 20] })
        }).addTo(map);

        var control = L.Routing.control({
            waypoints: [],
            router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1' }),
            lineOptions: { styles: [{color: '#00ff00', opacity: 0.8, weight: 10}] },
            language: 'es',
            addWaypoints: false
        }).addTo(map);

        async function calcularRutas() {
            const start = document.getElementById('origin').value;
            const end = document.getElementById('destination').value;
            const g1 = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${start},Cuba`).then(r=>r.json());
            const g2 = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${end},Cuba`).then(r=>r.json());

            if(g1[0] && g2[0]) {
                const p1 = L.latLng(g1[0].lat, g1[0].lon);
                const p2 = L.latLng(g2[0].lat, g2[0].lon);
                
                if(confirm("¿Desea la ruta más rápida por autopista?")) {
                   control.setWaypoints([p1, p2]);
                   map.flyTo(p1, 15);
                   colocarParchesRojos(p1);
                }
            }
        }

        function colocarParchesRojos(center) {
            // Coloca muros visuales en calles que NO son la ruta para evitar desvíos
            L.rectangle([[center.lat+0.001, center.lng+0.001], [center.lat+0.002, center.lng+0.002]], {
                color: "red", weight: 1, fillColor: 'red', fillOpacity: 0.7
            }).addTo(map).bindPopup("NO ENTRAR - DESVÍO");
        }

        function iniciarGPS() {
            if (!navigator.geolocation) return alert("GPS no soportado");
            
            navigator.geolocation.watchPosition(pos => {
                const lat = pos.coords.latitude;
                const lng = pos.coords.longitude;
                const speed = pos.coords.speed ? Math.round(pos.coords.speed * 3.6) : 0;
                
                document.getElementById('speed').innerText = speed;
                
                if (speed > 1) { // Solo mueve el mapa si el carro real se mueve
                    const newPos = L.latLng(lat, lng);
                    carMarker.setLatLng(newPos);
                    map.setView(newPos, 17);
                    hablarOnce("Traslado en progreso a " + speed + " kilómetros por hora");
                }
            }, err => console.error(err), { enableHighAccuracy: true });
        }

        let lastText = "";
        function hablarOnce(t) {
            if(t !== lastText) {
                const u = new SpeechSynthesisUtterance(t);
                u.lang = 'es-US';
                window.speechSynthesis.speak(u);
                lastText = t;
            }
        }

        function borrarRastro() {
            if(confirm("¿Borrar todos los datos de navegación?")) {
                localStorage.clear();
                window.location.href = "/";
            }
        }

        document.addEventListener('contextmenu', e => e.preventDefault());
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return f"""<body style="background:#000; color:white; text-align:center; font-family:sans-serif; padding:50px;">
    <h1>AL CIELO</h1><p>MAY ROGA LLC</p>
    <a href="/checkout/price_1Sv5uXBOA5mT4t0PtV7RaYCa" style="display:block; background:#0056b3; color:white; padding:20px; margin:10px; text-decoration:none; border-radius:10px;">10 DÍAS - $15</a>
    <a href="/checkout/price_1Sv69jBOA5mT4t0PUA7yiisS" style="display:block; background:#0056b3; color:white; padding:20px; margin:10px; text-decoration:none; border-radius:10px;">28 DÍAS - $25</a>
    </body>"""

@app.route("/checkout/<pid>")
def checkout(pid):
    session = stripe.checkout.Session.create(
        payment_method_types=["card"], mode="payment",
        line_items=[{"price": pid, "quantity": 1}],
        success_url=f"{BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=BASE_URL
    )
    return redirect(session.url)

@app.route("/success")
def success():
    time.sleep(10)
    return redirect(f"/link/{request.args.get('session_id')}")

@app.route("/link/<session_id>")
def link_redirect(session_id):
    lid = get_license_by_session(session_id)
    return redirect(f"/activar/{lid}") if lid else ("Procesando...", 404)

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    if request.method == "POST":
        set_active_device(link_id, request.json.get("device_id"))
        return jsonify({"status": "OK", "map_url": f"/viewer/{link_id}"})
    return render_template_string("<button onclick='act()'>ACEPTAR TÉRMINOS Y NAVEGAR</button><script>function act(){fetch('',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:crypto.randomUUID()})}).then(r=>r.json()).then(d=>window.location.href=d.map_url)}</script>")

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    return render_template_string(VIEWER_HTML, expira=lic[1]) if lic else ("Denegado", 403)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
