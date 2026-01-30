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
    html = """<h2>AL CIELO by May Roga LLC</h2><ul>"""
    for price_id, (precio, dias, desc) in PLANES.items():
        html += f'<li><a href="/checkout/{price_id}">{desc} – ${precio} / {dias} días</a></li>'
    html += "</ul>"
    return html

@app.route("/checkout/<price_id>")
def checkout(price_id):
    if price_id not in PLANES: return "Error", 404
    
    # BYPASS PARA ADMIN (Acceso Directo)
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
    time.sleep(5)
    return redirect(f"/link/{session_id}")

@app.route("/link/<session_id>")
def link_redirect(session_id):
    link_id = get_license_by_session(session_id)
    if not link_id:
        return "Confirmando pago con Stripe... Refresca en 5 segundos.", 404
    return redirect(f"/activar/{link_id}")

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Licencia inválida", 404
    expira = lic[1]

    if request.method == "POST":
        data = request.json
        if not data.get("legal_ok"): return jsonify({"error": "Acepta términos"}), 403
        device_id = data.get("device_id")
        set_active_device(link_id, device_id)
        return jsonify({"status": "OK", "map_url": f"/viewer/{link_id}"})

    return render_template_string("""
        <h3>Activación AL CIELO</h3>
        <p>Expira: {{expira}}</p>
        <button onclick="activar()">ACTIVAR SERVICIO</button>
        <script>
        async function activar(){
            const device_id = localStorage.getItem("device_id") || crypto.randomUUID();
            localStorage.setItem("device_id", device_id);
            const res = await fetch("", {
                method:"POST",
                headers:{"Content-Type":"application/json"},
                body:JSON.stringify({device_id:device_id, legal_ok:true})
            });
            const data = await res.json();
            if(res.ok) window.location.href = data.map_url;
        }
        </script>
    """, expira=expira)

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Acceso Denegado", 403
    expira = lic[1]

    return render_template_string("""
    <h3>AL CIELO – Navegador de Cuba</h3>
    <p>Licencia válida hasta: {{expira}}</p>
    <p><b>Uso privado:</b> El mapa solo puede visualizarse. No se permite descargar.</p>
    <div id="map" style="height:90vh;"></div>
    <input id="start" placeholder="Dirección de inicio" style="width:45%; margin-top:5px;">
    <input id="end" placeholder="Destino" style="width:45%; margin-top:5px;">
    <button onclick="calcularRuta()">Calcular Ruta</button>

    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css"/>
    <script src="https://unpkg.com/leaflet-control-geocoder/dist/Control.Geocoder.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/leaflet-control-geocoder/dist/Control.Geocoder.css"/>

    <script>
        var map = L.map('map').setView([21.5, -79.0], 7);

        // Tile layer desde OpenStreetMap
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: 'AL CIELO by May Roga LLC',
            maxZoom: 18
        }).addTo(map);

        var control = null;

        function calcularRuta(){
            var start = document.getElementById("start").value;
            var end = document.getElementById("end").value;
            if(!start || !end){ alert("Ingresa inicio y destino"); return; }

            // Geocodificación de direcciones
            var geocoder = L.Control.Geocoder.nominatim();
            geocoder.geocode(start, function(resultsStart){
                if(resultsStart.length === 0){ alert("Inicio no encontrado"); return; }
                var latlngStart = resultsStart[0].center;

                geocoder.geocode(end, function(resultsEnd){
                    if(resultsEnd.length === 0){ alert("Destino no encontrado"); return; }
                    var latlngEnd = resultsEnd[0].center;

                    if(control) map.removeControl(control);
                    control = L.Routing.control({
                        waypoints: [latlngStart, latlngEnd],
                        routeWhileDragging: true,
                        language: 'es',
                        showAlternatives: true
                    }).addTo(map);

                    // Voz en español
                    control.on('routesfound', function(e){
                        var steps = e.routes[0].instructions;
                        if(!steps) return;
                        steps.forEach(function(step){
                            var utter = new SpeechSynthesisUtterance(step.text);
                            utter.lang = 'es-ES';
                            speechSynthesis.speak(utter);
                        });
                    });
                });
            });
        }

        // Prevención descarga y menú derecho
        map.getContainer().addEventListener('contextmenu', function(e){ e.preventDefault(); });
    </script>
    """, expira=expira)

@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except: return "Error", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        price_id = stripe.checkout.Session.list_line_items(session["id"]).data[0].price.id
        dias = PLANES.get(price_id, [0, 10])[1]
        link_id = str(uuid.uuid4())[:8]
        expira = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        create_license(link_id, session["id"], expira)
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
