import os
import uuid
import time
import stripe
from flask import Flask, request, jsonify, redirect, render_template_string
from datetime import datetime, timedelta
from database import init_db, create_license, get_license_by_link, get_license_by_session, add_device, set_active_device

# ================= CONFIGURACIÓN =================
app = Flask(__name__)
init_db()

# Claves de Entorno (Asegúrate de ponerlas en Render)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY") # Necesaria para mapas en vivo
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
        <p>Seleccione su plan de asesoría:</p>
    """
    for pid, (cost, days, name) in PLANES.items():
        html += f'<div style="margin:10px;"><a href="/checkout/{pid}" style="padding:10px 20px; background:blue; color:white; text-decoration:none; border-radius:5px;">{name} - ${cost}</a></div>'
    html += "</body>"
    return html

@app.route("/checkout/<price_id>")
def checkout(price_id):
    if price_id not in PLANES: return "Plan inválido", 404
    
    # BYPASS DIRECTO PARA ADMIN
    if price_id == "price_1Sv6H2BOA5mT4t0PppizlRAK":
        link_id = str(uuid.uuid4())[:8]
        expira = (datetime.utcnow() + timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
        create_license(link_id, f"ADMIN_{link_id}", expira)
        return redirect(f"/activar/{link_id}")

    # PROCESO NORMAL STRIPE
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
        return "<h3>Procesando licencia...</h3><script>setTimeout(()=>location.reload(), 5000);</script>", 200
    return redirect(f"/activar/{link_id}")

# ================= ACTIVACIÓN Y VISOR EN VIVO =================

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Licencia no encontrada", 404
    
    if request.method == "POST":
        data = request.json
        device_id = data.get("device_id")
        set_active_device(link_id, device_id)
        return jsonify({"status": "OK", "redirect": f"/viewer/{link_id}"})

    return render_template_string("""
        <body style="font-family:sans-serif; text-align:center; padding:20px;">
            <h3>AL CIELO - Activación</h3>
            <p>Licencia válida hasta: {{expira}}</p>
            <div style="border:1px solid #ccc; padding:15px; margin:20px auto; max-width:400px;">
                <p><small>Al activar, acepta que es residente/ciudadano de USA y que el uso es personal.</small></p>
                <button onclick="activar()" style="padding:15px; cursor:pointer;">ACTIVAR SERVICIO</button>
            </div>
            <script>
            async function activar(){
                const devId = localStorage.getItem("device_id") || crypto.randomUUID();
                localStorage.setItem("device_id", devId);
                const res = await fetch("", {
                    method:"POST",
                    headers:{"Content-Type":"application/json"},
                    body:JSON.stringify({device_id: devId, legal_ok: true})
                });
                const data = await res.json();
                if(data.status === "OK") window.location.href = data.redirect;
            }
            </script>
        </body>
    """, expira=lic[1])

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Acceso prohibido", 403
    
    # INTERFAZ CON GOOGLE MAPS EN VIVO
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>AL CIELO - Live Tracking</title>
            <meta name="viewport" content="initial-scale=1.0, user-scalable=no">
            <meta charset="utf-8">
            <style>
                #map { height: 100vh; width: 100%; }
                .panel { position: absolute; top: 10px; left: 10px; z-index: 5; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 6px rgba(0,0,0,.3); }
            </style>
        </head>
        <body>
            <div class="panel">
                <b>AL CIELO BY MAY ROGA</b><br>
                <small>Licencia activa hasta: {{expira}}</small><br>
                <button onclick="location.href='/'">Borrar Sesión</button>
            </div>
            <div id="map"></div>
            <script async defer src="https://maps.googleapis.com/maps/api/js?key={{key}}&callback=initMap"></script>
            <script>
                function initMap() {
                    var cuba = {lat: 21.5218, lng: -77.7812};
                    var map = new google.maps.Map(document.getElementById('map'), {
                        zoom: 7,
                        center: cuba,
                        mapTypeId: 'hybrid' // Vista Satélite + Calles para mayor detalle
                    });
                    
                    if (navigator.geolocation) {
                        navigator.geolocation.watchPosition(function(position) {
                            var pos = {
                                lat: position.coords.latitude,
                                lng: position.coords.longitude
                            };
                            new google.maps.Marker({position: pos, map: map, title: "Tu ubicación"});
                            map.setCenter(pos);
                        });
                    }
                }
            </script>
        </body>
        </html>
    """, key=GOOGLE_MAPS_API_KEY, expira=lic[1])

# ================= WEBHOOK Y CIERRE =================

@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except: return "Error", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        items = stripe.checkout.Session.list_line_items(session["id"])
        price_id = items.data[0].price.id
        days = PLANES.get(price_id, [0, 10])[1]
        
        link_id = str(uuid.uuid4())[:8]
        expira = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        create_license(link_id, session["id"], expira)
        
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
