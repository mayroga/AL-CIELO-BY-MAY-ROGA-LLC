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
    <title>AL CIELO - Navegación Profesional</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css" />
    <style>
        body { margin:0; background:#000; font-family: 'Segoe UI', sans-serif; color:white; overflow:hidden; }
        #map { height: 70vh; width: 100%; border-bottom: 3px solid #0056b3; }
        .panel { height: 30vh; background:#111; padding:10px; display:flex; flex-direction:column; gap:5px; position:relative; }
        .search-box { display:flex; gap:5px; }
        input { flex:1; padding:10px; border-radius:6px; border:1px solid #333; background:#222; color:white; font-size:14px; }
        .btn-group { display:flex; gap:5px; }
        button { flex:1; padding:12px; border-radius:6px; font-weight:bold; border:none; cursor:pointer; color:white; }
        .btn-search { background:#333; }
        .btn-nav { background:#0056b3; display:none; }
        #instrucciones { font-size:14px; color:#00ff00; text-align:center; font-weight:bold; text-transform: uppercase; }
        #velocimetro { position:absolute; top:-60px; right:10px; background:rgba(0,0,0,0.8); padding:10px; border-radius:50%; border:2px solid #0056b3; width:40px; height:40px; text-align:center; line-height:40px; font-size:14px; z-index:1000; }
        .leaflet-routing-container { background: #222 !important; color: white !important; font-size: 12px; max-height: 150px !important; }
        .car-icon { font-size: 35px; text-shadow: 2px 2px 4px #000; transition: all 0.5s linear; }
    </style>
</head>
<body oncontextmenu="return false;">
    <div id="map"></div>
    <div id="velocimetro">0<br><small>km/h</small></div>
    <div class="panel">
        <div id="instrucciones">LISTO PARA TRASLADO EN CUBA</div>
        <div class="search-box">
            <input id="origen" placeholder="Tu ubicación">
            <input id="destino" placeholder="Destino final">
        </div>
        <div class="btn-group">
            <button class="btn-search" onclick="buscarRutas()">BUSCAR RUTAS</button>
            <button id="btnNav" class="btn-nav" onclick="activarNavegacionGPS()">INICIAR NAVEGACIÓN</button>
        </div>
        <div style="font-size:9px; color:#555; display:flex; justify-content:space-between; margin-top:5px;">
            <span>MAY ROGA LLC | USA JURISDICTION</span>
            <span>EXP: {{expira}}</span>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    <script>
        var map = L.map('map', { zoomControl: false }).setView([21.5, -79.5], 7);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);

        var control = L.Routing.control({
            waypoints: [],
            router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1', profile: 'car' }),
            lineOptions: { styles: [{color: '#00ff00', opacity: 0.8, weight: 8}] },
            showAlternatives: true,
            altLineOptions: { styles: [{color: '#ffa500', opacity: 0.5, weight: 6}] },
            language: 'es'
        }).addTo(map);

        var carMarker = L.marker([0,0], {
            icon: L.divIcon({html: '🚗', className: 'car-icon', iconAnchor: [17, 17]})
        }).addTo(map);

        async function geocode(query) {
            if(!query) return null;
            const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${query},Cuba`);
            const d = await r.json();
            return d.length > 0 ? L.latLng(d[0].lat, d[0].lon) : null;
        }

        async function buscarRutas() {
            const p1 = await geocode(document.getElementById('origen').value);
            const p2 = await geocode(document.getElementById('destino').value);
            if(p1 && p2) {
                control.setWaypoints([p1, p2]);
                document.getElementById('btnNav').style.display = 'block';
                hablar("Rutas encontradas. Seleccione la mejor opción y presione Iniciar.");
            }
        }

        function activarNavegacionGPS() {
            hablar("Navegación iniciada. El mapa se moverá con usted.");
            if ("geolocation" in navigator) {
                navigator.geolocation.watchPosition(pos => {
                    const latlng = [pos.coords.latitude, pos.coords.longitude];
                    const speed = Math.round(pos.coords.speed * 3.6) || 0;
                    
                    document.getElementById('velocimetro').innerHTML = speed + "<br><small>km/h</small>";
                    
                    // Solo mover si hay movimiento real
                    if(speed > 1) {
                        carMarker.setLatLng(latlng);
                        map.setView(latlng, 17);
                        verificarDesvios(latlng);
                    }
                }, null, { enableHighAccuracy: true });
            }
        }

        function verificarDesvios(currentPos) {
            // Lógica de "Parche Rojo" para calles prohibidas
            // Si el usuario se aleja más de 30m de la ruta trazada
            const routePoints = control.getPlan().getWaypoints();
            // (Simplificado para el ejemplo: marca un área de advertencia visual)
            L.rectangle(map.getBounds(), {color: "red", weight: 0, fillOpacity: 0.05, interactive: false}).addTo(map);
        }

        function hablar(t) {
            const u = new SpeechSynthesisUtterance(t);
            u.lang = 'es-ES';
            window.speechSynthesis.speak(u);
        }

        // Blindaje de Seguridad
        document.addEventListener('contextmenu', e => e.preventDefault());
        const exp = new Date("{{expira}}");
        if (new Date() > exp) {
            alert("SISTEMA BLOQUEADO - LICENCIA EXPIRADA");
            window.location.href = "/";
        }
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return f"""
    <body style="background:#000; color:white; text-align:center; font-family:sans-serif; padding:50px;">
        <h1 style="color:#0056b3;">AL CIELO</h1><p>May Roga LLC</p>
        <div style="margin:20px;"><a href="/checkout/price_1Sv5uXBOA5mT4t0PtV7RaYCa" style="display:block; padding:15px; background:#222; color:white; text-decoration:none; border-radius:10px;">10 DÍAS - $15.00</a></div>
        <div style="margin:20px;"><a href="/checkout/price_1Sv69jBOA5mT4t0PUA7yiisS" style="display:block; padding:15px; background:#0056b3; color:white; text-decoration:none; border-radius:10px;">28 DÍAS - $25.00</a></div>
        <div style="margin:20px;"><a href="/checkout/price_1Sv6H2BOA5mT4t0PppizlRAK" style="display:block; padding:15px; background:#333; color:white; text-decoration:none; border-radius:10px;">ADMIN ACCESS - $0.00</a></div>
    </body>
    """

@app.route("/checkout/<pid>")
def checkout(pid):
    if pid == "price_1Sv6H2BOA5mT4t0PppizlRAK":
        lid = str(uuid.uuid4())[:8]
        exp = (datetime.utcnow() + timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
        create_license(lid, f"ADMIN_{lid}", exp)
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
    time.sleep(10)
    return redirect(f"/link/{request.args.get('session_id')}")

@app.route("/link/<session_id>")
def link_redirect(session_id):
    lid = get_license_by_session(session_id)
    return redirect(f"/activar/{lid}") if lid else ("Confirmando pago...", 404)

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    if request.method == "POST":
        set_active_device(link_id, request.json.get("device_id"))
        return jsonify({"status": "OK", "map_url": f"/viewer/{link_id}"})
    return render_template_string("<body style='background:#000;color:white;text-align:center;padding:50px;'><h2>AL CIELO - Términos</h2><p>Uso exclusivo para traslado en Cuba bajo leyes USA.</p><button onclick='act()' style='padding:20px;background:#0056b3;color:white;border:none;border-radius:10px;'>ACEPTAR Y ENTRAR</button><script>function act(){ fetch('',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:crypto.randomUUID()})}).then(r=>r.json()).then(d=>window.location.href=d.map_url)}</script></body>")

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Denegado", 403
    return render_template_string(VIEWER_HTML, expira=lic[1])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
