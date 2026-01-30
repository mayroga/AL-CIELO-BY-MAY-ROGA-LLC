import os
import uuid
import time
import stripe
from flask import Flask, request, jsonify, redirect, render_template_string
from datetime import datetime, timedelta
from database import init_db, create_license, get_license_by_link, get_license_by_session, add_device, set_active_device

# ================= CONFIGURACIÓN =================
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

# ================= RUTAS DE ACCESO =================
@app.route("/")
def home():
    html = """
    <body style="font-family:sans-serif; text-align:center; padding:50px;">
        <h2>AL CIELO by May Roga LLC</h2>
        <p>Seleccione su plan para activar la asesoría y el mapa:</p>
        <div style="display:inline-block; text-align:left;">
    """
    for price_id, (precio, dias, desc) in PLANES.items():
        html += f'<p>• <a href="/checkout/{price_id}" style="text-decoration:none; font-weight:bold; color:#007bff;">{desc} – ${precio} USD</a></p>'
    html += "</div></body>"
    return html

@app.route("/checkout/<price_id>")
def checkout(price_id):
    if price_id not in PLANES: return "Plan no válido", 404
    
    # BYPASS DIRECTO PARA ADMIN
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
    time.sleep(5) # Tiempo para que el webhook procese
    return redirect(f"/link/{session_id}")

@app.route("/link/<session_id>")
def link_redirect(session_id):
    link_id = get_license_by_session(session_id)
    if not link_id:
        return "<h3>Procesando licencia...</h3><script>setTimeout(()=>location.reload(), 5000);</script>", 404
    return redirect(f"/activar/{link_id}")

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Enlace expirado o inválido", 404
    
    if request.method == "POST":
        data = request.json
        if not data.get("legal_ok"): return jsonify({"error": "Debe aceptar términos"}), 403
        set_active_device(link_id, data.get("device_id"))
        return jsonify({"status": "OK", "map_url": f"/viewer/{link_id}"})

    return render_template_string("""
        <body style="font-family:sans-serif; padding:30px;">
            <h3>Activación de Servicio - AL CIELO</h3>
            <p>Su acceso vence el: <b>{{expira}}</b></p>
            <label><input type="checkbox" id="legal"> Acepto el blindaje legal (Residente/Ciudadano USA)</label><br><br>
            <button onclick="activar()" style="padding:10px 20px; background:#28a745; color:white; border:none; border-radius:5px; cursor:pointer;">ACTIVAR AHORA</button>
            <script>
            async function activar(){
                if(!document.getElementById("legal").checked) return alert("Acepte términos");
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
        </body>
    """, expira=lic[1])

# ================= VISOR GOOGLE MAPS STYLE =================
@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Acceso Denegado", 403
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>AL CIELO - Mapa Profesional</title>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
            <style>
                body { margin: 0; padding: 0; }
                #map { height: 100vh; width: 100vw; }
                .admin-panel { position: absolute; top: 10px; right: 10px; z-index: 1000; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.3); }
            </style>
        </head>
        <body>
            <div class="admin-panel">
                <b>AL CIELO</b><br>
                <small>Vence: {{expira}}</small><br>
                <button onclick="location.href='/'" style="margin-top:5px; font-size:10px;">Cerrar</button>
            </div>
            <div id="map"></div>
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <script>
                var map = L.map('map', { center: [21.5, -79.0], zoom: 7 });

                // Capas tipo Google Maps
                var googleSat = L.tileLayer('http://{s}.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}',{
                    maxZoom: 20,
                    subdomains:['mt0','mt1','mt2','mt3']
                });

                var googleStreets = L.tileLayer('http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',{
                    maxZoom: 20,
                    subdomains:['mt0','mt1','mt2','mt3']
                });

                // Capa Offline Local (Si existe el mbtiles procesado)
                var localCuba = L.tileLayer('/static/maps/cuba/{z}/{x}/{y}.png', {
                    maxZoom: 18,
                    tms: true,
                    attribution: 'AL CIELO Offline'
                });

                googleSat.addTo(map); // Inicia con Satélite Híbrido

                var baseMaps = {
                    "Satélite (Google)": googleSat,
                    "Calles (Google)": googleStreets,
                    "Offline Local": localCuba
                };

                L.control.layers(baseMaps).addTo(map);
            </script>
        </body>
        </html>
    """, expira=lic[1])

# ================= WEBHOOK =================
@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception as e: return str(e), 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        items = stripe.checkout.Session.list_line_items(session["id"])
        price_id = items.data[0].price.id
        dias = PLANES.get(price_id, [0, 10])[1]
        link_id = str(uuid.uuid4())[:8]
        expira = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        create_license(link_id, session["id"], expira)
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
