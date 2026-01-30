import os
import uuid
import time
import stripe
from flask import Flask, request, jsonify, redirect, render_template_string
from datetime import datetime, timedelta
from database import init_db, create_license, get_license_by_link, get_license_by_session, add_device, set_active_device

app = Flask(__name__, static_url_path='/static', static_folder='static')
init_db()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"

stripe.api_key = STRIPE_SECRET_KEY

PLANES = {
    "price_1Sv5uXBOA5mT4t0PtV7RaYCa": [15.00, 10, "Asesoría 10 Días"],
    "price_1Sv69jBOA5mT4t0PUA7yiisS": [25.00, 28, "Asesoría 28 Días"],
    "price_1Sv6H2BOA5mT4t0PppizlRAK": [0.00, 20, "Acceso Admin (Bypass)"]
}

@app.route("/")
def home():
    html = """<body style='font-family:sans-serif; text-align:center;'><h2>AL CIELO by May Roga LLC</h2><ul>"""
    for price_id, (precio, dias, desc) in PLANES.items():
        html += f'<li><a href="/checkout/{price_id}">{desc} – ${precio} / {dias} días</a></li>'
    html += "</ul></body>"
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
    session_id = request.args.get("session_id")
    time.sleep(10) 
    return redirect(f"/link/{session_id}")

@app.route("/link/<session_id>")
def link_redirect(session_id):
    link_id = get_license_by_session(session_id)
    if not link_id: return "Confirmando... Refresca en 5 segundos.", 404
    return redirect(f"/activar/{link_id}")

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Licencia inválida", 404
    if request.method == "POST":
        set_active_device(link_id, request.json.get("device_id"))
        return jsonify({"status": "OK", "map_url": f"/viewer/{link_id}"})
    return render_template_string("""
        <h3>Activación AL CIELO</h3>
        <p>Expira: {{expira}}</p>
        <button onclick="activar()">ACTIVAR SERVICIO</button>
        <script>
        async function activar(){
            const id = localStorage.getItem("device_id") || crypto.randomUUID();
            localStorage.setItem("device_id", id);
            const res = await fetch("", {
                method:"POST",
                headers:{"Content-Type":"application/json"},
                body:JSON.stringify({device_id:id, legal_ok:true})
            });
            const data = await res.json();
            if(res.ok) window.location.href = data.map_url;
        }
        </script>
    """, expira=lic[1])

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Acceso Denegado", 403
    return render_template_string("""
    <head>
        <title>AL CIELO - Navegación Live</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
        <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css"/>
        <style>
            #map {height: 85vh; width: 100%;}
            .ui {padding: 10px; background: #eee; display: flex; gap: 5px;}
            .admin-btn {background: red; color: white; border: none; padding: 5px 10px; cursor: pointer;}
        </style>
    </head>
    <body>
        <div class="ui">
            <input id="destino" placeholder="Destino en Cuba (ej: Varadero)" style="flex-grow:1; padding:10px;">
            <button onclick="buscarDestino()" style="padding:10px;">IR AHORA</button>
            <button class="admin-btn" onclick="borrarTodo()">BORRAR</button>
        </div>
        <div id="map"></div>

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.min.js"></script>

        <script>
        var map = L.map('map').setView([23.1136, -82.3666], 12);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

        var control = L.Routing.control({
            waypoints: [],
            router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1' }),
            language: 'es',
            show: true
        }).addTo(map);

        function hablar(texto) {
            var msg = new SpeechSynthesisUtterance(texto);
            msg.lang = 'es-ES';
            window.speechSynthesis.speak(msg);
        }

        function buscarDestino() {
            var dest = document.getElementById("destino").value;
            if(!dest) return;

            // Buscamos ubicación actual
            map.locate({setView: true, maxZoom: 16});
            
            map.on('locationfound', function(e) {
                var miPos = e.latlng;
                fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${dest}+Cuba`)
                .then(res => res.json())
                .then(data => {
                    if(data.length > 0) {
                        var target = L.latLng(data[0].lat, data[0].lon);
                        control.setWaypoints([miPos, target]);
                        hablar("Iniciando navegación hacia " + dest);
                    } else {
                        alert("No se encontró el lugar en Cuba");
                    }
                });
            });
        }

        function borrarTodo() {
            if(confirm("¿Desea borrar los datos de sesión y regresar?")) {
                localStorage.clear();
                window.location.href = "/";
            }
        }

        map.getContainer().addEventListener('contextmenu', e => e.preventDefault());
        </script>
    </body>
    """, expira=lic[1])

@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except: return "Error", 400
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        line_items = stripe.checkout.Session.list_line_items(session["id"])
        price_id = line_items.data[0].price.id
        dias = PLANES.get(price_id, [0, 10])[1]
        link_id = str(uuid.uuid4())[:8]
        expira = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        create_license(link_id, session["id"], expira)
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
