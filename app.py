import os
import uuid
import stripe
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timedelta

app = Flask(__name__)

# ================== ENV ==================
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
ADMIN_USER = os.getenv("ADMIN_USERNAME")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"

stripe.api_key = STRIPE_SECRET_KEY

# ================== DB EN MEMORIA ==================
db_licencias = {}  # link_id -> datos licencia
db_stripe_links = {}  # checkout_session_id -> link_id

# ================== PLANES ==================
PLANES = {
    "bJe8wOaof8dR7sXaPF7Vm0k": 10,  # $0.50 / 10 días (solo admin/test)
    "dRm6oG8g7cu76oT1f57Vm0i": 10,  # $15 / 10 días
    "14A3cudArfGj9B51f57Vm0j": 28   # $25 / 28 días
}

# ================== ROOT ==================
@app.route("/")
def home():
    return """
    <h2>AL CIELO by May Roga LLC</h2>
    <p>Compra tu acceso y recibe automáticamente tu link de activación.</p>
    """

# ================== STRIPE WEBHOOK ==================
@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session.get("id")
        checkout_url = session.get("url", "")

        # Detectar plan por URL
        plan_dias = None
        for key, dias in PLANES.items():
            if key in checkout_url:
                plan_dias = dias
                break

        if not plan_dias:
            plan_dias = 10  # fallback

        # Crear licencia
        link_id = str(uuid.uuid4())[:8]
        expiracion = datetime.now() + timedelta(days=plan_dias)

        db_licencias[link_id] = {
            "devices": [],
            "active_device": None,
            "expira": expiracion.strftime("%Y-%m-%d %H:%M:%S")
        }

        db_stripe_links[session_id] = link_id

        print("✅ LICENCIA CREADA:", link_id)

    return jsonify({"status": "ok"}), 200

# ================== ACTIVACIÓN ==================
@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    if link_id not in db_licencias:
        return "Licencia no válida o vencida.", 404

    lic = db_licencias[link_id]

    if request.method == "POST":
        data = request.json
        device_id = data.get("device_id")
        legal_ok = data.get("legal_ok")

        if not legal_ok:
            return jsonify({"error": "Debe aceptar términos legales"}), 403

        if device_id not in lic["devices"]:
            if len(lic["devices"]) >= 2:
                return jsonify({"error": "Límite de dispositivos alcanzado"}), 403
            lic["devices"].append(device_id)

        lic["active_device"] = device_id

        return jsonify({
            "status": "OK",
            "expira": lic["expira"],
            "map_url": f"{BASE_URL}/static/maps/cuba_full.mbtiles"
        })

    return render_template_string("""
        <h2>AL CIELO – Activación</h2>
        <p>Licencia válida hasta: {{expira}}</p>
        <p>Máx. 2 dispositivos · Solo 1 activo</p>
        <label>
          <input type="checkbox" id="legal"> Acepto términos legales
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
            alert("✅ Link de activación listo. Descargando mapa...");
            window.location.href = data.map_url;
          } else {
            alert(data.error);
          }
        }
        </script>
    """, expira=lic["expira"])

# ================== RUN ==================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
