import os, uuid, time, stripe
from flask import Flask, request, jsonify, redirect, render_template_string
from datetime import datetime, timedelta
from database import init_db, create_license, get_license_by_link, get_license_by_session, set_active_device

app = Flask(__name__, static_url_path='/static', static_folder='static')
init_db()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"
stripe.api_key = STRIPE_SECRET_KEY

PLANES = {
    "price_1Sv5uXBOA5mT4t0PtV7RaYCa": [15.00, 10, "Plan 10 Días"],
    "price_1Sv69jBOA5mT4t0PUA7yiisS": [25.00, 28, "Plan 28 Días"],
    "price_1Sv6H2BOA5mT4t0PppizlRAK": [0.00, 20, "Prueba Admin ($0.00)"]
}

VIEWER_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <title>AL CIELO - Navegación de Precisión</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css" />
    <style>
        body { margin:0; background:#000; font-family: 'Segoe UI', sans-serif; color:white; overflow:hidden; }
        #map { height: 65vh; width: 100%; border-bottom: 3px solid #0056b3; }
        .panel { height: 35vh; background:#111; padding:10px; display:flex; flex-direction:column; gap:5px; }
        .telemetria { display: flex; justify-content: space-around; background: #222; padding: 8px; border-radius: 8px; border: 1px solid #0af; color: #0af; font-family: monospace; }
        .search-box { display:flex; gap:5px; }
        input { flex:1; padding:10px; border-radius:6px; border:1px solid #333; background:#222; color:white; font-size:14px; }
        .btn-group { display: flex; gap: 5px; }
        .btn-nav { flex: 1.5; background:#0056b3; color:white; border:none; padding:12px; border-radius:6px; font-weight:bold; cursor:pointer; font-size:14px; }
        .btn-alt { flex: 1; background:#444; color:white; border:none; padding:12px; border-radius:6px; font-weight:bold; cursor:pointer; font-size:12px; }
        #instrucciones { font-size:14px; color:#00ff00; font-weight:bold; text-align:center; min-height:1.2em; text-transform: uppercase; }
        .status-bar { font-size:10px; color:#555; display:flex; justify-content:space-between; margin-top:5px; }
        .car-icon { filter: drop-shadow(0 0 8px #fff); transition: all 0.5s linear; }
        .leaflet-routing-container { display: none; }
    </style>
</head>
<body oncontextmenu="return false;">
    <div id="map"></div>
    <div class="panel">
        <div id="instrucciones">LISTO PARA EXPLORAR CUBA</div>
        <div class="telemetria">
            <div>VEL: <b id="vel" style="font-size:18px;">0</b> km/h</div>
            <div>DIST: <b id="dist" style="font-size:18px;">0.0</b> km</div>
            <div>MODO: <b id="modo">ESPERA</b></div>
        </div>
        <div class="search-box">
            <input id="origen" placeholder="Punto de Origen">
            <input id="destino" placeholder="Punto de Destino">
        </div>
        <div class="btn-group">
            <button class="btn-alt" onclick="buscarRutas()">VER RUTAS</button>
            <button class="btn-nav" onclick="iniciarNavegacion()">INICIAR NAVEGACIÓN REAL</button>
        </div>
        <div class="status-bar">
            <span>MAY ROGA LLC | V2.1 SENSOR</span>
            <span>EXPIRA: {{expira}}</span>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    <script>
        var map = L.map('map', { zoomControl: false }).setView([21.5, -79.5], 7);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

        var carMarker = L.marker([0,0], {
            icon: L.divIcon({html: '<div style="font-size:40px;">🚗</div>', className: 'car-icon', iconSize: [50, 50]})
        }).addTo(map);

        var control = L.Routing.control({
            waypoints: [],
            router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1', profile: 'car' }),
            lineOptions: { styles: [{color: '#00ff00', opacity: 0.8, weight: 10}] },
            showAlternatives: true,
            language: 'es'
        }).addTo(map);

        async function geocode(q) {
            const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${q},Cuba`);
            const d = await r.json(); return d.length > 0 ? L.latLng(d[0].lat, d[0].lon) : null;
        }

        async function buscarRutas() {
            const p1 = await geocode(document.getElementById('origen').value);
            const p2 = await geocode(document.getElementById('destino').value);
            if(p1 && p2) {
                control.setWaypoints([p1, p2]);
                hablar("Rutas calculadas. Seleccione la mejor opción y presione Iniciar.");
            }
        }

        control.on('routesfound', function(e) {
            var d = (e.routes[0].summary.totalDistance / 1000).toFixed(1);
            document.getElementById('dist').innerText = d;
        });

        function iniciarNavegacion() {
            if (!navigator.geolocation) return alert("Active el GPS");
            document.getElementById('modo').innerText = "VIVO";
            hablar("Sistema Al Cielo conectado al satélite. Iniciando monitoreo.");
            
            navigator.geolocation.watchPosition(pos => {
                const latlng = [pos.coords.latitude, pos.coords.longitude];
                const vel = pos.coords.speed ? Math.round(pos.coords.speed * 3.6) : 0;
                
                document.getElementById('vel').innerText = vel;
                carMarker.setLatLng(latlng);
                map.setView(latlng, 18);

                // Bloqueo de desvío (Parche Rojo)
                verificarDesvio(latlng);
            }, null, { enableHighAccuracy: true });
        }

        function verificarDesvio(pos) {
            // Genera parches rojos en calles laterales para marcar "No Pasar"
            var rect = L.rectangle(L.latLng(pos).toBounds(100), {
                color: "red", weight: 2, fillOpacity: 0.1, dashArray: '5, 10'
            }).addTo(map);
            setTimeout(() => map.removeLayer(rect), 3000);
        }

        function hablar(t) {
            const u = new SpeechSynthesisUtterance(t);
            u.lang = 'es-ES'; window.speechSynthesis.speak(u);
        }

        const expira = new Date("{{expira}}");
        if (new Date() > expira) { alert("LICENCIA VENCIDA"); window.location.href = "/"; }
        document.addEventListener('contextmenu', e => e.preventDefault());
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    html = '<div style="max-width:400px; margin:auto; text-align:center; font-family:sans-serif; background:#000; color:white; padding:40px; border-radius:20px; border: 2px solid #0056b3;">'
    html += '<h1>AL CIELO</h1><p>MAY ROGA LLC</p><hr>'
    for pid, (p, d, n) in PLANES.items():
        color = "#0056b3" if p > 0 else "#333"
        html += f'<a href="/checkout/{pid}" style="display:block; background:{color}; color:white; padding:18px; margin:15px 0; text-decoration:none; border-radius:12px; font-weight:bold; font-size:18px;">{n} - ${p}</a>'
    html += '<p style="font-size:12px; color:#444;">PRECISION TRACKING SYSTEM</p></div>'
    return html

@app.route("/checkout/<pid>")
def checkout(pid):
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
    time.sleep(8)
    return redirect(f"/link/{request.args.get('session_id')}")

@app.route("/link/<session_id>")
def link_redirect(session_id):
    lid = get_license_by_session(session_id)
    return redirect(f"/activar/{lid}") if lid else ("Confirmando...", 404)

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    if request.method == "POST":
        set_active_device(link_id, request.json.get("device_id"))
        return jsonify({"status": "OK", "map_url": f"/viewer/{link_id}"})
    return render_template_string("<body style='background:#000; color:white; text-align:center;'><h3>TÉRMINOS MAY ROGA LLC</h3><button style='padding:15px; background:#0056b3; color:white; border:none; border-radius:10px;' onclick='act()'>ACEPTAR Y ENTRAR AL SISTEMA</button><script>function act(){ fetch('',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:crypto.randomUUID()})}).then(r=>r.json()).then(d=>window.location.href=d.map_url)}</script></body>")

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "DENEGADO", 403
    return render_template_string(VIEWER_HTML, expira=lic[1])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
