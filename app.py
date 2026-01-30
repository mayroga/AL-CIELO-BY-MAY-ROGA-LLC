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
        #map { height: 70vh; width: 100%; border-bottom: 3px solid #0056b3; z-index: 1; }
        
        /* Mini Mapa Flotante */
        #mini-map { 
            position: absolute; top: 10px; right: 10px; 
            width: 120px; height: 160px; 
            border: 2px solid #0056b3; border-radius: 8px; 
            z-index: 1000; background: #000; overflow: hidden;
            box-shadow: 0 0 15px rgba(0,0,0,0.5);
        }

        .panel { height: 30vh; background:#111; padding:10px; display:flex; flex-direction:column; gap:5px; position: relative; z-index: 10; }
        .telemetria { display: flex; justify-content: space-around; background: #222; padding: 5px; border-radius: 5px; font-family: monospace; color: #0af; font-size: 12px; }
        .search-box { display:flex; gap:5px; }
        input { flex:1; padding:10px; border-radius:6px; border:1px solid #333; background:#222; color:white; font-size:13px; }
        .btn-group { display: flex; gap: 5px; }
        .btn-nav { flex:1; background:#0056b3; color:white; border:none; padding:12px; border-radius:6px; font-weight:bold; cursor:pointer; }
        .btn-alt { flex:1; background:#444; color:white; border:none; padding:12px; border-radius:6px; font-weight:bold; cursor:pointer; }
        #instrucciones { font-size:14px; color:#00ff00; font-weight:bold; text-align:center; min-height:1.5em; text-transform: uppercase; }
        .status-bar { font-size:9px; color:#444; display:flex; justify-content:space-between; margin-top:2px; }
        .leaflet-routing-container { display: none; }
    </style>
</head>
<body oncontextmenu="return false;">
    <div id="mini-map"></div>
    <div id="map"></div>
    
    <div class="panel">
        <div id="instrucciones">ESPERANDO DESTINO...</div>
        <div class="telemetria">
            <span>VELOCIDAD: <b id="vel">0</b> km/h</span>
            <span>ALTITUD: <b id="alt">0</b> m</span>
        </div>
        <div class="search-box">
            <input id="origen" placeholder="Punto de Salida">
            <input id="destino" placeholder="Punto de Destino">
        </div>
        <div class="btn-group">
            <button class="btn-alt" onclick="buscarRutas()">BUSCAR RUTAS</button>
            <button class="btn-nav" onclick="iniciarSeguimiento()">NAVEGAR AHORA</button>
        </div>
        <div class="status-bar">
            <span>© MAY ROGA LLC | USA JURISDICTION</span>
            <span>LICENCIA EXPIRA: {{expira}}</span>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    <script>
        // Mapa Principal (Real)
        var map = L.map('map', { zoomControl: false }).setView([23.1136, -82.3666], 12);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

        // Mini Mapa (Simulado)
        var miniMap = L.map('mini-map', { zoomControl: false, attributionControl: false }).setView([23.1136, -82.3666], 10);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(miniMap);

        var carIcon = L.divIcon({html: '<div style="font-size:25px;">🚗</div>', className: 'car-icon', iconSize: [30, 30]});
        var mainCar = L.marker([0,0], {icon: carIcon}).addTo(map);
        var miniCar = L.marker([0,0], {icon: L.divIcon({html: '🚗', iconSize:[15,15]})}).addTo(miniMap);

        var control = L.Routing.control({
            waypoints: [],
            router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1' }),
            lineOptions: { styles: [{color: '#00ff00', opacity: 1, weight: 8}] },
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
            if(p1 && p2) control.setWaypoints([p1, p2]);
        }

        function iniciarSeguimiento() {
            if (!navigator.geolocation) return alert("Active el GPS");
            hablar("Navegación Al Cielo activada. Sincronizando con vehículo real.");
            
            navigator.geolocation.watchPosition(pos => {
                const latlng = [pos.coords.latitude, pos.coords.longitude];
                const speed = pos.coords.speed ? Math.round(pos.coords.speed * 3.6) : 0;
                
                document.getElementById('vel').innerText = speed;
                document.getElementById('alt').innerText = Math.round(pos.coords.altitude || 0);

                if (speed > 0.5) {
                    mainCar.setLatLng(latlng);
                    miniCar.setLatLng(latlng);
                    map.setView(latlng, 17);
                    miniMap.setView(latlng, 14);
                    marcarParcheRojo(latlng);
                }
            }, null, { enableHighAccuracy: true });
        }

        function marcarParcheRojo(pos) {
            var patch = L.circle(pos, { color: 'red', fillColor: '#f03', fillOpacity: 0.3, radius: 40 }).addTo(map);
            setTimeout(() => map.removeLayer(patch), 2000);
        }

        function hablar(t) {
            const u = new SpeechSynthesisUtterance(t);
            u.lang = 'es-ES';
            window.speechSynthesis.speak(u);
        }

        // Blindaje
        if (new Date() > new Date("{{expira}}")) {
            alert("EXPIRADO"); window.location.href = "/";
        }
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return f"""
    <body style="background:#000; color:white; text-align:center; font-family:sans-serif; padding-top:50px;">
        <h1 style="color:#0056b3;">AL CIELO</h1><p>MAY ROGA LLC</p>
        <div style="margin:20px;"><a href="/checkout/price_1Sv5uXBOA5mT4t0PtV7RaYCa" style="padding:15px; background:#0056b3; color:white; text-decoration:none; border-radius:8px; display:block; width:200px; margin:auto;">10 DÍAS - $15.00</a></div>
        <div style="margin:20px;"><a href="/checkout/price_1Sv69jBOA5mT4t0PUA7yiisS" style="padding:15px; background:#0056b3; color:white; text-decoration:none; border-radius:8px; display:block; width:200px; margin:auto;">28 DÍAS - $25.00</a></div>
        <div style="margin:20px;"><a href="/checkout/price_1Sv6H2BOA5mT4t0PppizlRAK" style="padding:15px; background:#333; color:white; text-decoration:none; border-radius:8px; display:block; width:200px; margin:auto;">ADMIN TEST - $0.00</a></div>
    </body>
    """

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
    time.sleep(5)
    return redirect(f"/link/{request.args.get('session_id')}")

@app.route("/link/<session_id>")
def link_redirect(session_id):
    lid = get_license_by_session(session_id)
    return redirect(f"/activar/{lid}") if lid else ("Error", 404)

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    if request.method == "POST":
        set_active_device(link_id, request.json.get("device_id"))
        return jsonify({"status": "OK", "map_url": f"/viewer/{link_id}"})
    return render_template_string("<body style='background:#000;color:white;text-align:center;'><h3>TÉRMINOS MAY ROGA LLC</h3><button style='padding:20px;' onclick='act()'>ACEPTAR Y ENTRAR</button><script>function act(){ fetch('',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:crypto.randomUUID()})}).then(r=>r.json()).then(d=>window.location.href=d.map_url)}</script></body>")

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Acceso Denegado", 403
    return render_template_string(VIEWER_HTML, expira=lic[1])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
