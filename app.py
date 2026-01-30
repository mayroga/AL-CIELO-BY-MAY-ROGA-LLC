import os
import uuid
from datetime import datetime, timedelta
from flask import Flask, redirect, request, jsonify, render_template_string
import stripe

from database import (
    init_db,
    create_license,
    get_license_by_session
)

# ================= APP =================
app = Flask(__name__)
init_db()

# ================= ENV =================
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
BASE_URL = os.getenv("BASE_URL", "https://al-cielo-by-may-roga-llc.onrender.com")

# ================= PLANES =================
PLANES = {
    "10dias": {
        "price_id": "price_1Sv5uXBOA5mT4t0PtV7RaYCa",
        "precio": 15,
        "dias": 10,
        "nombre": "Asesoría 10 Días"
    },
    "28dias": {
        "price_id": "price_1Sv69jBOA5mT4t0PUA7yiisS",
        "precio": 25,
        "dias": 28,
        "nombre": "Asesoría 28 Días"
    },
    "admin": {
        "price_id": "price_1Sv6H2BOA5mT4t0PppizlRAK",
        "precio": 0,
        "dias": 20,
        "nombre": "Acceso Admin (Bypass)"
    }
}

# ================= HOME =================
@app.route("/")
def home():
    return render_template_string("""
    <h2>AL CIELO by May Roga LLC</h2>
    <p><b>Compra tu acceso y recibe tu activación automática:</b></p>

    {% for k, p in planes.items() %}
      <form action="/checkout/{{k}}" method="POST">
        <button style="padding:10px;margin:10px;font-size:16px">
          {{p.nombre}} – ${{p.precio}} / {{p.dias}} días
        </button>
      </form>
    {% endfor %}
    """, planes=PLANES)

# ================= CHECKOUT =================
@app.route("/checkout/<plan>", methods=["POST"])
def checkout(plan):
    if plan not in PLANES:
        return "Plan inválido", 404

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price": PLANES[plan]["price_id"],
            "quantity": 1
        }],
        success_url=f"{BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/"
    )

    return redirect(session.url, code=303)

# ================= SUCCESS =================
@app.route("/success")
def success():
    session_id = request.args.get("session_id")
    if not session_id:
        return "Sesión inválida", 400

    return f"""
    <h3>Pago realizado con éxito</h3>
    <p>Activando tu acceso…</p>
    <script>
      setTimeout(() => {{
        window.location.href = "/link/{session_id}";
      }}, 3000);
    </script>
    """

# ================= STRIPE WEBHOOK =================
@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        return "Webhook inválido", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        line_items = stripe.checkout.Session.list_line_items(session["id"])
        price_id = line_items.data[0].price.id

        dias = 10
        for p in PLANES.values():
            if p["price_id"] == price_id:
                dias = p["dias"]

        link_id = str(uuid.uuid4())[:8]
        expires = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")

        create_license(link_id, session["id"], expires)
        print("✅ LICENCIA CREADA:", link_id)

    return jsonify({"ok": True})

# ================= LINK =================
@app.route("/link/<session_id>")
def link(session_id):
    link_id = get_license_by_session(session_id)
    if not link_id:
        return "Licencia aún no lista. Refresca en 5 segundos.", 404

    return redirect(f"/activar/{link_id}")

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
