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
        #map { height: 75vh; width: 100%; border-bottom: 3px solid #0056b3; cursor: crosshair; }
        .panel { height: 25vh; background:#111; padding:15px; display:flex; flex-direction:column; gap:8px; }
        .search-box { display:flex; gap:5px; }
        input { flex:1; padding:10px; border-radius:6px; border:1px solid #333; background:#222; color:white; font-size:14px; }
        .btn-nav { background:#0056b3; color:white; border:none; padding:12px; border-radius:6px; font-weight:bold; cursor:pointer; }
        #instrucciones { font-size:15px; color:#00ff00; font-weight:bold; text-align:center; min-height:1.5em; text-transform: uppercase; }
        .status-bar { font-size:10px; color:#444; display:flex; justify-content:space-between; margin-top:5px; }
        /* Ocultar elementos innecesarios */
        .leaflet-routing-container { display: none; }
    </style>
</head>
<body oncontextmenu="return false;">
    <div id="map"></div>
    <div class="panel">
        <div id="instrucciones">ESPERANDO DESTINO EN CUBA...</div>
        <div class="search-box">
            <input id="origen" placeholder="Origen (Ej: Lawton)">
            <input id="destino" placeholder="Destino (Ej: Varadero)">
        </div>
        <button class="btn-nav" onclick="iniciarNavegacion()">INICIAR TRASLADO SEGURO</button>
        <div class="status-bar">
            <span>© MAY ROGA LLC | USA JURISDICTION</span>
            <span>EXPIRA: {{expira}}</span>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    <script>
        var map = L.map('map', { zoomControl: false }).setView([23.1136, -82.3666], 12);
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);

        var control = L.Routing.control({
            waypoints: [],
            router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1' }),
            lineOptions: { styles: [{color: '#00ff00', opacity: 1, weight: 10}] },
            language: 'es',
            createMarker: function(i, wp) {
                return L.marker(wp.latLng, {draggable: false}).bindPopup(i === 0 ? "INICIO" : "DESTINO");
            }
        }).addTo(map);

        async function geocode(query) {
            const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${query},Cuba`);
            const d = await r.json();
            return d.length > 0 ? L.latLng(d[0].lat, d[0].lon) : null;
        }

        async function iniciarNavegacion() {
            const p1 = await geocode(document.getElementById('origen').value);
            const p2 = await geocode(document.getElementById('destino').value);
            
            if(p1 && p2) {
                control.setWaypoints([p1, p2]);
                hablar("Ruta calculada. Iniciando traslado simulado por la isla.");
            }
        }

        control.on('routesfound', function(e) {
            var route = e.routes[0];
            simularTraslado(route);
        });

        function simularTraslado(route) {
            var coords = route.coordinates;
            var instructions = route.instructions;
            let step = 0;
            let coordIdx = 0;

            // Marcador del "Carrito" de May Roga LLC
            var carIcon = L.divIcon({html: '🚗', className: 'car-icon', iconSize: [25, 25]});
            var carMarker = L.marker(coords[0], {icon: carIcon}).addTo(map);

            function mover() {
                if (coordIdx < coords.length) {
                    var currentCoord = coords[coordIdx];
                    carMarker.setLatLng(currentCoord);
                    map.setView(currentCoord, 17); // Zoom de calle tipo Google

                    // Verificar instrucciones de voz basadas en la posición
                    if (step < instructions.length && coordIdx >= instructions[step].index) {
                        var texto = instructions[step].text;
                        document.getElementById('instrucciones').innerText = texto;
                        hablar(texto);
                        
                        // Marcar desvíos prohibidos visualmente (Cruces en Rojo)
                        marcarZonasRojas(currentCoord);
                        step++;
                    }

                    coordIdx++;
                    // Tiempo realista: Simulamos 40km/h aprox.
                    setTimeout(mover, 400); 
                } else {
                    hablar("Ha llegado a su destino. Traslado finalizado.");
                }
            }
            mover();
        }

        function marcarZonasRojas(pos) {
            // Lógica para resaltar visualmente que no se debe salir de la ruta
            var circle = L.circle(pos, {
                color: 'red',
                fillColor: '#f03',
                fillOpacity: 0.2,
                radius: 50
            }).addTo(map);
            setTimeout(() => map.removeLayer(circle), 2000);
        }

        function hablar(texto) {
            if ('speechSynthesis' in window) {
                const u = new SpeechSynthesisUtterance(texto);
                u.lang = 'es-ES'; // Español formal
                u.rate = 0.9;
                window.speechSynthesis.speak(u);
            }
        }

        // Blindaje Legal: Auto-destrucción y Anti-copia
        const expira = new Date("{{expira}}");
        if (new Date() > expira) {
            alert("LICENCIA VENCIDA. Borrando datos.");
            localStorage.clear();
            window.location.href = "/";
        }
        document.addEventListener('contextmenu', e => e.preventDefault());
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
        <div style="margin:20px;"><a href="/checkout/price_1Sv6H2BOA5mT4t0PppizlRAK" style="padding:15px; background:#333; color:white; text-decoration:none; border-radius:8px;">ADMIN TEST - $0.00</a></div>
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
    return redirect(f"/activar/{lid}") if lid else ("Error de enlace", 404)

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    if request.method == "POST":
        set_active_device(link_id, request.json.get("device_id"))
        return jsonify({"status": "OK", "map_url": f"/viewer/{link_id}"})
    return render_template_string("<h3>Términos May Roga LLC</h3><button onclick='act()'>ACEPTAR Y ENTRAR</button><script>function act(){ fetch('',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:crypto.randomUUID()})}).then(r=>r.json()).then(d=>window.location.href=d.map_url)}</script>")

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Denegado", 403
    return render_template_string(VIEWER_HTML, expira=lic[1])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
