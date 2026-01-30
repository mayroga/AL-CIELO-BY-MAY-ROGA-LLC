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
    "price_1Sv6H2BOA5mT4t0PppizlRAK": [0.00, 20, "Prueba Admin ($0.00)"]
}

VIEWER_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <title>AL CIELO - Navegación Dual</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <style>
        body { margin:0; background:#000; font-family: 'Segoe UI', sans-serif; color:white; overflow:hidden; }
        #map { height: 70vh; width: 100%; border-bottom: 3px solid #0056b3; }
        
        /* Estilo del Minimapa de Simulación */
        #minimap { 
            position: absolute; top: 10px; right: 10px; width: 120px; height: 160px; 
            border: 2px solid #00ff00; border-radius: 8px; z-index: 1000; background: #000;
            box-shadow: 0 0 15px rgba(0,255,0,0.5);
        }

        .panel { height: 30vh; background:#111; padding:10px; display:flex; flex-direction:column; gap:5px; }
        .telemetria { display: flex; justify-content: space-around; background: #222; padding: 5px; border-radius: 5px; font-family: monospace; color: #0af; border: 1px solid #333; }
        .search-box { display:flex; gap:5px; }
        input { flex:1; padding:10px; border-radius:6px; border:1px solid #333; background:#222; color:white; font-size:13px; }
        .btn-nav { background:#0056b3; color:white; border:none; padding:12px; border-radius:6px; font-weight:bold; cursor:pointer; width: 100%; }
        #instrucciones { font-size:14px; color:#00ff00; font-weight:bold; text-align:center; min-height:1.2em; text-transform: uppercase; }
        .status-bar { font-size:9px; color:#444; display:flex; justify-content:space-between; margin-top:2px; }
    </style>
</head>
<body oncontextmenu="return false;">
    <div id="map"></div>
    <div id="minimap"></div> <div class="panel">
        <div id="instrucciones">SISTEMA AL CIELO - ESPERANDO</div>
        <div class="telemetria">
            <span>V: <b id="vel">0</b> km/h</span>
            <span>A: <b id="alt">0</b> m</span>
            <span>ESTADO: <b id="modo">IDLE</b></span>
        </div>
        <div class="search-box">
            <input id="origen" placeholder="Origen">
            <input id="destino" placeholder="Destino">
        </div>
        <button class="btn-nav" onclick="iniciarNavegacion()">ACTIVAR TRASLADO SEGURO</button>
        <div class="status-bar">
            <span>MAY ROGA LLC | JURISDICCIÓN USA</span>
            <span>VENCE: {{expira}}</span>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        // Mapa Principal (Seguimiento Real)
        var map = L.map('map', { zoomControl: false }).setView([23.1136, -82.3666], 12);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

        // Minimapa (Simulación Visual)
        var miniMap = L.map('minimap', { zoomControl: false, attributionControl: false }).setView([23.1136, -82.3666], 15);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(miniMap);

        var carIcon = L.divIcon({html: '🚗', className: 'car-icon', iconSize: [30, 30]});
        var mainMarker = L.marker([0,0], {icon: carIcon}).addTo(map);
        var miniMarker = L.marker([0,0], {icon: carIcon}).addTo(miniMap);

        async function geocode(query) {
            const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${query},Cuba`);
            const d = await r.json();
            return d.length > 0 ? [d[0].lat, d[0].lon] : null;
        }

        function iniciarNavegacion() {
            if (!navigator.geolocation) return alert("Active GPS");
            document.getElementById('modo').innerText = "LIVE";
            hablar("Iniciando traslados sincronizados.");

            navigator.geolocation.watchPosition(pos => {
                const latlng = [pos.coords.latitude, pos.coords.longitude];
                const speed = Math.round((pos.coords.speed || 0) * 3.6);
                
                // Actualizar Telemetría Real
                document.getElementById('vel').innerText = speed;
                document.getElementById('alt').innerText = Math.round(pos.coords.altitude || 0);

                if (speed > 1) { // Solo mover si hay movimiento real
                    mainMarker.setLatLng(latlng);
                    miniMarker.setLatLng(latlng);
                    map.setView(latlng, 17);
                    miniMap.setView(latlng, 18);
                    
                    // Parche rojo si hay desvío (Lógica visual)
                    marcarZonaSegura(latlng);
                }
            }, null, { enableHighAccuracy: true });
        }

        function marcarZonaSegura(pos) {
            var zone = L.circle(pos, {color: 'red', weight: 2, fillOpacity: 0.1, radius: 40}).addTo(map);
            setTimeout(() => map.removeLayer(zone), 2000);
        }

        function hablar(t) {
            const u = new SpeechSynthesisUtterance(t);
            u.lang = 'es-ES';
            window.speechSynthesis.speak(u);
        }

        const exp = new Date("{{expira}}");
        if (new Date() > exp) { alert("LICENCIA VENCIDA"); window.location.href = "/"; }
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return f"""
    <body style="background:#000; color:white; text-align:center; font-family:sans-serif; padding-top:50px;">
        <h1>AL CIELO</h1><p>May Roga LLC</p>
        <div style="margin:20px;"><a href="/checkout/price_1Sv5uXBOA5mT4t0PtV7RaYCa" style="padding:15px; background:#0056b3; color:white; text-decoration:none; border-radius:8px;">10 DÍAS - $15.00</a></div>
        <div style="margin:20px;"><a href="/checkout/price_1Sv69jBOA5mT4t0PUA7yiisS" style="padding:15px; background:#0056b3; color:white; text-decoration:none; border-radius:8px;">28 DÍAS - $25.00</a></div>
    </body>
    """

@app.route("/checkout/<pid>")
def checkout(pid):
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
    return render_template_string("<button onclick='act()'>ACEPTAR TÉRMINOS Y ENTRAR</button><script>function act(){ fetch('',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:crypto.randomUUID()})}).then(r=>r.json()).then(d=>window.location.href=d.map_url)}</script>")

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Acceso Denegado", 403
    return render_template_string(VIEWER_HTML, expira=lic[1])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
