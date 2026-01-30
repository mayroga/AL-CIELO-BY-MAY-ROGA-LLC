import os
import uuid
import time
import stripe
from flask import Flask, request, jsonify, render_template_string, redirect, send_file
from datetime import datetime, timedelta
from database import init_db, create_license, get_license_by_link, get_license_by_session, add_device, set_active_device

# ================= APP =================
app = Flask(__name__, static_url_path='/static', static_folder='static')
init_db()

# ================= ENV =================
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"

stripe.api_key = STRIPE_SECRET_KEY

# ================= PLANES =================
PLANES = {
    "price_1Sv5uXBOA5mT4t0PtV7RaYCa": [15.00, 10, "Asesoría 10 Días"],
    "price_1Sv69jBOA5mT4t0PUA7yiisS": [25.00, 28, "Asesoría 28 Días"],
    "price_1Sv6H2BOA5mT4t0PppizlRAK": [0.00, 20, "Acceso Admin (Bypass)"]
}

# ================= HOME =================
@app.route("/")
def home():
    html = """
    <h2>AL CIELO by May Roga LLC</h2>
    <p>Compra tu acceso y recibe tu activación automática:</p>
    <ul>
    """
    for price_id, (precio, dias, desc) in PLANES.items():
        # Link de Stripe Checkout directo
        html += f'<li><a href="/checkout/{price_id}">{desc} – ${precio} / {dias} días</a></li>'
    html += "</ul>"
    return html

# ================= CHECKOUT =================
@app.route("/checkout/<price_id>")
def checkout(price_id):
    if price_id not in PLANES:
        return "Producto no encontrado", 404

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price": price_id,
            "quantity": 1
        }],
        success_url=f"{BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=BASE_URL
    )
    return redirect(session.url)

# ================= SUCCESS =================
@app.route("/success")
def success():
    session_id = request.args.get("session_id")
    if not session_id:
        return "No hay sesión", 400

    # Espera de 10-15s para que la licencia se cree
    time.sleep(12)

    return redirect(f"/link/{session_id}")

# ================= LINK REDIRECT =================
@app.route("/link/<session_id>")
def link_redirect(session_id):
    link_id = get_license_by_session(session_id)
    if not link_id:
        return "Procesando tu licencia…<br>Espera unos segundos para que se cree tu acceso automáticamente.", 404
    return redirect(f"/activar/{link_id}")

# ================= ACTIVACIÓN =================
@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    lic = get_license_by_link(link_id)
    if not lic:
        return "Licencia inválida o vencida", 404

    # Ajustar según tu DB: (id, session_id, expira)
    expira = lic[2]

    if request.method == "POST":
        data = request.json
        device_id = data.get("device_id")
        legal_ok = data.get("legal_ok")

        if not legal_ok:
            return jsonify({"error": "Debe aceptar términos legales"}), 403

        # Manejo simple de dispositivos: 2 max
        devices = lic[3] if len(lic) > 3 else []
        if device_id not in devices:
            if len(devices) >= 2:
                return jsonify({"error": "Máximo 2 dispositivos permitidos"}), 403
            add_device(link_id, device_id)

        set_active_device(link_id, device_id)

        # Map URL con streaming (TileServer interno)
        return jsonify({
            "status": "OK",
            "expira": expira,
            "map_url": f"{BASE_URL}/viewer/{link_id}"
        })

    return render_template_string("""
    <h2>AL CIELO – Activación</h2>
    <p>Licencia válida hasta: {{expira}}</p>
    <p>Máx. 2 dispositivos · Solo 1 activo</p>
    <p><b>Blindaje legal:</b> Uso privado del mapa. No se entrega copia descargable.</p>
    <label>
      <input type="checkbox" id="legal"> Acepto términos
    </label><br><br>
    <button onclick="activar()">Activar</button>

    <script>
    async function activar(){
      if(!document.getElementById("legal").checked){
        alert("Debe aceptar los términos");
        return;
      }
      const device_id = localStorage.getItem("device_id") || crypto.randomUUID();
      localStorage.setItem("device_id", device_id);

      const res = await fetch("", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({device_id:device_id, legal_ok:true})
      });
      const data = await res.json();
      if(res.ok){
        alert("Licencia activada! Abriendo visor...");
        window.location.href = data.map_url;
      } else {
        alert(data.error);
      }
    }
    </script>
    """, expira=expira)

# ================= VISOR DE MAPA =================
@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic:
        return "Licencia inválida o vencida", 404

    expira = lic[2]

    # Render del visor HTML con streaming de tiles (no descarga)
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
      <title>Mapa Cuba – AL CIELO</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    </head>
    <body>
      <h3>AL CIELO – Visor de Mapas</h3>
      <p>Licencia válida hasta: {{expira}}</p>
      <div id="map" style="height: 90vh;"></div>
      <script>
        var map = L.map('map').setView([21.5, -79.0], 6); // Cuba centro
        L.tileLayer('/static/maps/{tile}/{z}/{x}/{y}.png', {
          maxZoom: 18,
          attribution: "AL CIELO – Uso privado",
          tms: true
        }).addTo(map);

        // Simulación navegación por voz (placeholder)
        console.log("Modo bajo consumo: streaming, no descarga");

      </script>
    </body>
    </html>
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
        dias = PLANES.get(price_id, [0, 10])[1]

        link_id = str(uuid.uuid4())[:8]
        expira = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        create_license(link_id, session_id, expira)
        print(f"✅ LICENCIA CREADA INMEDIATA: {link_id}")

    return jsonify({"ok": True})

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
