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
    <title>AL CIELO - Traslado Profesional Cuba</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css" />
    <style>
        body { margin:0; background:#000; font-family: sans-serif; color:white; overflow:hidden; }
        #map { height: 70vh; width: 100%; border-bottom: 4px solid #0056b3; }
        .panel { height: 30vh; background:#111; padding:10px; display:flex; flex-direction:column; gap:5px; }
        .search-box { display:flex; gap:5px; }
        input { flex:1; padding:12px; border-radius:8px; border:none; background:#222; color:white; font-weight:bold; }
        .btn-main { background:#0056b3; color:white; border:none; padding:12px; border-radius:8px; font-weight:bold; cursor:pointer; font-size:16px; }
        #instrucciones { font-size:14px; color:#00ff00; text-align:center; font-weight:bold; text-transform:uppercase; height:2.4em; overflow:hidden; }
        .telemetria { display:flex; justify-content:space-around; background:#222; padding:8px; border-radius:8px; border:1px solid #333; }
        .dato { text-align:center; }
        .dato span { display:block; font-size:10px; color:#aaa; }
        .dato b { font-size:18px; color:#fff; }
        .car-icon { font-size: 35px; filter: drop-shadow(0 0 5px #fff); }
        .no-pass { background: rgba(255,0,0,0.6); border: 2px solid red; font-weight:bold; color:white; text-align:center; padding:2px; border-radius:4px; font-size:10px; }
        .leaflet-routing-alt { background:#222 !important; color:white !important; font-size:12px !important; }
    </style>
</head>
<body oncontextmenu="return false;">
    <div id="map"></div>
    <div class="panel">
        <div id="instrucciones">SISTEMA AL CIELO: INGRESE RUTA</div>
        <div class="telemetria">
            <div class="dato"><span>VELOCIDAD</span><b id="vel">0</b><small> km/h</small></div>
            <div class="dato"><span>DISTANCIA</span><b id="dist">0</b><small> km</small></div>
            <div class="dato"><span>ESTADO</span><b id="status" style="color:#00ff00;">LISTO</b></div>
        </div>
        <div class="search-box">
            <input id="origen" placeholder="ORIGEN">
            <input id="destino" placeholder="DESTINO">
        </div>
        <button class="btn-main" onclick="buscarRutas()">VER OPCIONES Y NAVEGAR</button>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    <script>
        var map = L.map('map', { zoomControl: false }).setView([21.5, -79.5], 7);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);

        var control = L.Routing.control({
            waypoints: [],
            router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1', profile: 'car' }),
            lineOptions: { styles: [{color: '#00ff00', opacity: 1, weight: 10}] },
            language: 'es',
            showAlternatives: true,
            altLineOptions: { styles: [{color: '#555', opacity: 0.6, weight: 6}] }
        }).addTo(map);

        var carMarker = L.marker([0,0], {icon: L.divIcon({className:'car-icon', html:'🚗', iconSize:[40,40]})});

        async function buscarRutas() {
            const p1 = await geocode(document.getElementById('origen').value);
            const p2 = await geocode(document.getElementById('destino').value);
            if(p1 && p2) {
                control.setWaypoints([p1, p2]);
                hablar("Seleccione una de las rutas disponibles en pantalla para iniciar.");
            }
        }

        async function geocode(q) {
            const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${q},Cuba`);
            const d = await r.json(); return d[0] ? L.latLng(d[0].lat, d[0].lon) : null;
        }

        control.on('routesfound', function(e) {
            hablar("Rutas encontradas. Mostrando alternativas.");
            const route = e.routes[0];
            document.getElementById('dist').innerText = (route.summary.totalDistance/1000).toFixed(1);
            
            // Iniciar seguimiento GPS real
            navigator.geolocation.watchPosition(pos => {
                const p = L.latLng(pos.coords.latitude, pos.coords.longitude);
                const v = pos.coords.speed ? (pos.coords.speed * 3.6).toFixed(0) : 0;
                actualizarNavegacion(p, v, route);
            }, err => console.log(err), { enableHighAccuracy: true });
        });

        function actualizarNavegacion(pos, velocidad, ruta) {
            carMarker.setLatLng(pos).addTo(map);
            map.setView(pos, 17);
            document.getElementById('vel').innerText = velocidad;
            document.getElementById('status').innerText = "EN MARCHA";

            // Buscar instrucción actual
            ruta.instructions.forEach(inst => {
                const distToStep = pos.distanceTo(ruta.coordinates[inst.index]);
                if(distToStep < 30) {
                    document.getElementById('instrucciones').innerText = inst.text;
                    hablar(inst.text);
                    ponerMurosDeContencion(ruta.coordinates[inst.index]);
                }
            });
        }

        function ponerMurosDeContencion(centro) {
            // Parches rojos en calles laterales para evitar errores
            L.circle(centro, { color: 'red', fillColor: '#f03', fillOpacity: 0.5, radius: 40 })
                .bindTooltip("NO ENTRAR", {permanent: true, className: "no-pass"}).addTo(map);
        }

        function hablar(t) {
            const u = new SpeechSynthesisUtterance(t); u.lang = 'es-ES'; u.rate = 1;
            window.speechSynthesis.speak(u);
        }

        // Blindaje de Seguridad May Roga LLC
        const exp = new Date("{{expira}}");
        if(new Date() > exp) { localStorage.clear(); window.location.href="/"; }
        document.addEventListener('contextmenu', e => e.preventDefault());
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string("""
        <div style="background:#000; color:white; height:100vh; text-align:center; padding:50px; font-family:sans-serif;">
            <h1 style="color:#0056b3;">AL CIELO</h1><p>MAY ROGA LLC</p><hr style="border-color:#222;">
            {% for pid, (p, d, n) in planes.items() %}
                <a href="/checkout/{{pid}}" style="display:block; background:#0056b3; color:white; padding:20px; margin:20px; text-decoration:none; border-radius:10px; font-weight:bold;">{{n}} - ${{p}}</a>
            {% endfor %}
        </div>
    """, planes=PLANES)

@app.route("/checkout/<pid>")
def checkout(pid):
    if pid == "price_1Sv6H2BOA5mT4t0PppizlRAK":
        lid = str(uuid.uuid4())[:8]
        exp = (datetime.utcnow() + timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
        create_license(lid, f"ADMIN_{lid}", exp)
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
    return render_template_string("<h3>AL CIELO: TRASLADO SEGURO</h3><button onclick='act()'>ACEPTAR TÉRMINOS Y NAVEGAR</button><script>function act(){ fetch('',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:crypto.randomUUID()})}).then(r=>r.json()).then(d=>window.location.href=d.map_url)}</script>")

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Acceso Denegado", 403
    return render_template_string(VIEWER_HTML, expira=lic[1])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
