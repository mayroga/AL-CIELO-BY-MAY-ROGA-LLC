import os
import uuid
import stripe
from flask import Flask, request, jsonify, render_template_string, redirect
from datetime import datetime, timedelta

from database import (
    init_db,
    create_license,
    get_license_by_link,
    get_license_by_session,
    get_devices,
    add_device,
    set_active_device
)

app = Flask(__name__)
init_db()

# ================= ENV =================
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"

stripe.api_key = STRIPE_SECRET_KEY

# ================= PLANES =================
PLANES = {
    "price_1Sv5uXBOA5mT4t0PtV7RaYCa": 10,  # $15 / 10 días
    "price_1Sv69jBOA5mT4t0PUA7yiisS": 28,  # $25 / 28 días
    "price_1Sv6H2BOA5mT4t0PppizlRAK": 20   # $0 / 20 días (Admin)
}

LINKS_STRIPE = {
    "price_1Sv5uXBOA5mT4t0PtV7RaYCa": "https://buy.stripe.com/price_1Sv5uXBOA5mT4t0PtV7RaYCa",
    "price_1Sv69jBOA5mT4t0PUA7yiisS": "https://buy.stripe.com/price_1Sv69jBOA5mT4t0PUA7yiisS",
    "price_1Sv6H2BOA5mT4t0PppizlRAK": "https://buy.stripe.com/price_1Sv6H2BOA5mT4t0PppizlRAK"
}

# ================= HOME =================
@app.route("/")
def home():
    html = "<h2>AL CIELO by May Roga LLC</h2><p>Compra tu acceso y recibe tu activación automática:</p><ul>"
    for pid, url in LINKS_STRIPE.items():
        html += f'<li><a href="{url}">{url.split("/")[-1]}</a></li>'
    html += "</ul>"
    return html

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
        price_id = session["line_items"]["data"][0]["price"]["id"] if "line_items" in session else None

        dias = PLANES.get(price_id, 10)
        link_id = str(uuid.uuid4())[:8]
        expira = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")

        create_license(link_id, session_id, expira)
        print("✅ LICENCIA CREADA:", link_id)

    return jsonify({"ok": True})

# ================= REDIRECCIÓN =================
@app.route("/link/<session_id>")
def link_redirect(session_id):
    link_id = get_license_by_session(session_id)
    if not link_id:
        return "Licencia aún no disponible. Refresque en 10 segundos.", 404
    return redirect(f"{BASE_URL}/activar/{link_id}")

# ================= ACTIVACIÓN =================
@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    lic = get_license_by_link(link_id)
    if not lic:
        return "Licencia inválida o vencida", 404

    _, expira, _ = lic

    if request.method == "POST":
        data = request.json
        device_id = data.get("device_id")
        legal_ok = data.get("legal_ok")

        if not legal_ok:
            return jsonify({"error": "Debe aceptar términos legales"}), 403

        devices = get_devices(link_id)
        if device_id not in devices:
            if len(devices) >= 2:
                return jsonify({"error": "Máximo 2 dispositivos permitidos"}), 403
            add_device(link_id, device_id)

        set_active_device(link_id, device_id)

        return jsonify({
            "status": "OK",
            "expira": expira,
            "map_url": f"{BASE_URL}/static/maps/cuba_full.mbtiles"
        })

    return render_template_string("""
    <h2>AL CIELO – Activación</h2>
    <p>Licencia válida hasta: {{expira}}</p>
    <p>Máx. 2 dispositivos · Solo 1 activo</p>

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
      const id = localStorage.getItem("device_id") || crypto.randomUUID();
      localStorage.setItem("device_id", id);

      const res = await fetch("", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({device_id:id, legal_ok:true})
      });
      const data = await res.json();
      if(res.ok){
        window.location.href = data.map_url;
      } else {
        alert(data.error);
      }
    }
    </script>
    """, expira=expira)

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
