import os
import uuid
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, redirect, render_template_string

import stripe
from database import init_db, create_license, get_license_by_link, get_license_by_session

# ================= FLASK =================
app = Flask(__name__, static_url_path='/static', static_folder='static')
init_db()

# ================= ENV =================
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
BASE_URL = os.getenv("BASE_URL", "https://al-cielo-by-may-roga-llc.onrender.com")

stripe.api_key = STRIPE_SECRET_KEY

# ================= PLANES =================
PLANES = {
    "price_1Sv5uXBOA5mT4t0PtV7RaYCa": {"precio": 15.0, "dias": 10, "desc": "Asesoría 10 Días"},
    "price_1Sv69jBOA5mT4t0PUA7yiisS": {"precio": 25.0, "dias": 28, "desc": "Asesoría 28 Días"},
    "price_1Sv6H2BOA5mT4t0PppizlRAK": {"precio": 0.0, "dias": 20, "desc": "Acceso Admin (Bypass)"}
}

# ================= HOME =================
@app.route("/")
def home():
    html = """
    <h2>AL CIELO by May Roga LLC</h2>
    <p>Compra tu acceso y recibe tu activación automática:</p>
    <ul>
    """
    for price_id, plan in PLANES.items():
        # link clicable a Stripe Checkout
        html += f'<li><a href="https://buy.stripe.com/{price_id}" target="_blank">{plan["desc"]} – ${plan["precio"]} / {plan["dias"]} días</a></li>'
    html += "</ul>"
    html += "<p>📌 Nota: Tras completar el pago, serás redirigido automáticamente a tu visor de mapas.</p>"
    return html

# ================= SUCCESS =================
@app.route("/success")
def success():
    session_id = request.args.get("session_id")
    if not session_id:
        return "Sesión inválida", 400

    # Si ya existe licencia, redirige
    link_id = get_license_by_session(session_id)
    if link_id:
        return redirect(f"/viewer/{link_id}")

    # Crear licencia inmediata
    try:
        session = stripe.checkout.Session.retrieve(session_id, expand=["line_items"])
        line_items = session.line_items.data
        price_id = line_items[0].price.id
        plan = PLANES.get(price_id, {"dias": 10})
        dias = plan["dias"]

        link_id = str(uuid.uuid4())[:8]
        expira = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        create_license(link_id, session_id, expira)
        print(f"✅ LICENCIA CREADA INMEDIATA: {link_id}")

        # Dar un pequeño delay para que todo se registre (Stripe / DB)
        time.sleep(3)

        # Redirige automáticamente al visor
        return redirect(f"/viewer/{link_id}")

    except Exception as e:
        return f"Error creando licencia: {e}", 500

# ================= VIEWER =================
@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic:
        return "Licencia inválida o vencida", 404

    _, expira = lic

    return render_template_string("""
    <h2>AL CIELO – Visor de Mapas</h2>
    <p>Licencia válida hasta: {{expira}}</p>
    <p>📌 Uso exclusivo privado. No se permite descargar o redistribuir.</p>
    <div id="map" style="height: 80vh; width: 100%;"></div>

    <!-- Leaflet.js para mapas -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

    <script>
      const map = L.map('map', {zoomControl: true}).setView([23.1136, -82.3666], 7); // Cuba

      // Tiles en streaming desde el servidor (no descarga)
      L.tileLayer('/static/maps/{z}/{x}/{y}.png', {
        attribution: '&copy; May Roga LLC',
        maxZoom: 18,
        tms: false
      }).addTo(map);

      // Navegación tipo Google (orientación, voz opcional)
      function onLocationFound(e) {
        const radius = e.accuracy;
        L.marker(e.latlng).addTo(map)
          .bindPopup("Estás aquí (precisión ±" + radius + " m)").openPopup();
      }
      map.locate({setView: true, watch: true, maxZoom: 17});
      map.on('locationfound', onLocationFound);
    </script>
    """, expira=expira)

# ================= STRIPE WEBHOOK =================
@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        return jsonify({"error": "Webhook inválido"}), 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session["id"]
        line_items = stripe.checkout.Session.list_line_items(session_id)
        price_id = line_items.data[0].price.id
        dias = PLANES.get(price_id, {"dias": 10})["dias"]
        link_id = str(uuid.uuid4())[:8]
        expira = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        create_license(link_id, session_id, expira)
        print(f"✅ LICENCIA CREADA (WEBHOOK): {link_id}")

    return jsonify({"ok": True})

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
