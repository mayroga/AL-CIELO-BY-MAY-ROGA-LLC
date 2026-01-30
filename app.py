import os, uuid, time, stripe
from flask import Flask, request, jsonify, redirect, render_template_string
from datetime import datetime, timedelta
from database import init_db, create_license, get_license_by_link, get_license_by_session, set_active_device

app = Flask(__name__, static_url_path='/static', static_folder='static')
init_db()

# CONFIGURACIÓN DE SEGURIDAD - MAY ROGA LLC
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"
stripe.api_key = STRIPE_SECRET_KEY

PLANES = {
    "price_1Sv5uXBOA5mT4t0PtV7RaYCa": [15.00, 10, "Transportación 10 Días"],
    "price_1Sv69jBOA5mT4t0PUA7yiisS": [25.00, 28, "Transportación 28 Días"],
    "price_1Sv6H2BOA5mT4t0PppizlRAK": [0.00, 20, "Acceso Admin (Bypass)"]
}

VIEWER_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <title>AL CIELO - Sistema de Navegación Cuba</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css" />
    <style>
        body { margin:0; background:#000; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color:white; overflow:hidden; }
        #map { height: 75vh; width: 100%; border-bottom: 3px solid #0059b3; }
        .nav-panel { height: 25vh; background:#111; padding:15px; display:flex; flex-direction:column; gap:10px; }
        .search-group { display:flex; gap:8px; }
        input { flex:1; padding:15px; border-radius:8px; border:1px solid #333; background:#222; color:white; font-size:16px; }
        .btn-nav { background:#0059b3; color:white; border:none; padding:15px; border-radius:8px; font-weight:bold; width:100%; font-size:16px; cursor:pointer; }
        .info-bar { display:flex; justify-content:space-between; font-size:10px; color:#555; margin-top:5px; }
        /* Bloqueo de impresión y copia */
        @media print { body { display:none; } }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="nav-panel">
        <div class="search-group">
            <input id="destino" placeholder="¿A dónde vamos en Cuba? (Ej: Varadero)">
        </div>
        <button class="btn-nav" onclick="iniciarNavegacion()">INICIAR RUTA TRASLADO</button>
        <div class="info-bar">
            <span>MAY ROGA LLC - JURISDICCIÓN USA</span>
            <span>EXPIRA: {{expira}}</span>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    <script>
        // BOMBA DE TIEMPO: Auto-destrucción si expira
        const expiraStr = "{{expira}}";
        if (new Date() > new Date(expiraStr)) {
            alert("LICENCIA VENCIDA. Borrando datos de seguridad...");
            localStorage.clear();
            caches.keys().then(n => n.forEach(c => caches.delete(c)));
            window.location.href = "/";
        }

        // MAPA CONFIGURADO PARA TODA CUBA
        var map = L.map('map', { zoomControl: false }).setView([21.5, -79.5], 6);
        
        // Capas inteligentes (Caché Invisible)
        const tileUrl = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
        L.tileLayer(tileUrl, { maxZoom: 19 }).addTo(map);

        var control = L.Routing.control({
            waypoints: [],
            router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1' }),
            lineOptions: { styles: [{color: '#00ff00', opacity: 0.9, weight: 8}] },
            language: 'es',
            createMarker: function(i, wp) {
                return L.marker(wp.latLng, { draggable: true });
            }
        }).addTo(map);

        // GEOLOCALIZACIÓN EN TIEMPO REAL (MOVIMIENTO)
        map.locate({setView: true, maxZoom: 16, watch: true});

        async function iniciarNavegacion() {
            const dest = document.getElementById('destino').value;
            if(!dest) return;

            const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${dest},Cuba`);
            const data = await res.json();

            if(data[0]) {
                const start = map.getCenter();
                const end = L.latLng(data[0].lat, data[0].lon);
                control.setWaypoints([start, end]);
                
                // VOZ DE MANDO
                var msg = new SpeechSynthesisUtterance("Calculando traslado hacia " + dest + ". Siga la ruta verde.");
                msg.lang = 'es-US';
                window.speechSynthesis.speak(msg);
            } else {
                alert("Destino no localizado en la isla.");
            }
        }

        // PROTECCIÓN ANTI-COPIA
        document.addEventListener('contextmenu', e => e.preventDefault());
        document.onkeydown = function(e) {
            if(e.ctrlKey && (e.keyCode === 85 || e.keyCode === 83 || e.keyCode === 123)) return false;
        };
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    html = """<body style="background:#111; color:white; text-align:center; padding-top:50px; font-family:sans-serif;">
              <h2>AL CIELO by May Roga LLC</h2><p>Seleccione su Plan de Movimiento en Cuba</p>"""
    for pid, (precio, dias, desc) in PLANES.items():
        html += f'<div style="margin:20px;"><a href="/checkout/{pid}" style="display:inline-block; width:80%; padding:20px; background:#0059b3; color:white; text-decoration:none; border-radius:10px; font-weight:bold;">{desc} – ${precio}</a></div>'
    html += "</body>"
    return html

@app.route("/checkout/<price_id>")
def checkout(price_id):
    if price_id not in PLANES: return "Error", 404
    if price_id == "price_1Sv6H2BOA5mT4t0PppizlRAK":
        link_id = str(uuid.uuid4())[:8]
        expira = (datetime.utcnow() + timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
        create_license(link_id, f"ADMIN_{link_id}", expira)
        return redirect(f"/activar/{link_id}")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=BASE_URL
    )
    return redirect(session.url)

@app.route("/success")
def success():
    time.sleep(12) # Tiempo para Webhook
    return redirect(f"/link/{request.args.get('session_id')}")

@app.route("/link/<session_id>")
def link_redirect(session_id):
    link_id = get_license_by_session(session_id)
    return redirect(f"/activar/{link_id}") if link_id else "Procesando pago..."

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Licencia Inválida", 403
    if request.method == "POST":
        device_id = request.json.get("device_id")
        set_active_device(link_id, device_id)
        return jsonify({"status": "OK", "map_url": f"/viewer/{link_id}"})
    return render_template_string("""
        <body style="background:#000; color:white; text-align:center; padding:50px;">
            <h2>AL CIELO - ACTIVACIÓN</h2>
            <p>Al activar, este servicio quedará vinculado a este teléfono.</p>
            <button onclick="act()" style="padding:20px; background:green; color:white; border:none; border-radius:10px; cursor:pointer;">VINCULAR DISPOSITIVO Y ENTRAR</button>
            <script>
            async function act(){
                const d_id = localStorage.getItem("d_id") || crypto.randomUUID();
                localStorage.setItem("d_id", d_id);
                const r = await fetch("", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({device_id:d_id})});
                const res = await r.json();
                if(r.ok) window.location.href = res.map_url;
            }
            </script>
        </body>
    """)

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Acceso Denegado", 403
    return render_template_string(VIEWER_HTML, expira=lic[1])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
