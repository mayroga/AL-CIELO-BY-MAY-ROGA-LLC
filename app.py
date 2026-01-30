import os
import uuid
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, redirect, render_template_string
import stripe
from database import init_db, create_license, get_license_by_session

app = Flask(__name__)
init_db()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
BASE_URL = os.getenv("BASE_URL", "https://al-cielo-by-may-roga-llc.onrender.com")

PLANES = {
    "10": {"price_id": "price_1Sv5uXBOA5mT4t0PtV7RaYCa", "dias": 10, "precio": 15},
    "28": {"price_id": "price_1Sv69jBOA5mT4t0PUA7yiisS", "dias": 28, "precio": 25},
    "admin": {"price_id": "price_1Sv6H2BOA5mT4t0PppizlRAK", "dias": 20, "precio": 0}
}

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template_string("""
    <h2>AL CIELO by May Roga LLC</h2>
    <p>Selecciona tu acceso:</p>
    <ul>
        <li><a href="/pagar/10">Asesoría 10 días – $15</a></li>
        <li><a href="/pagar/28">Asesoría 28 días – $25</a></li>
        <li><a href="/pagar/admin">Acceso Admin</a></li>
    </ul>
    """)

# ---------------- CREAR SESIÓN DE PAGO ----------------
@app.route("/pagar/<plan>")
def pagar(plan):
    if plan not in PLANES:
        return "Plan inválido", 404
    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[{"price": PLANES[plan]["price_id"], "quantity": 1}],
        success_url=f"{BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/"
    )
    return redirect(session.url)

# ---------------- SUCCESS / ESPERA ----------------
@app.route("/success")
def success():
    session_id = request.args.get("session_id")
    if not session_id:
        return "Sesión inválida", 400
    return render_template_string("""
    <h2>Procesando tu licencia…</h2>
    <p>Espera unos segundos para que se cree tu acceso automáticamente.</p>
    <script>
    async function checkLicense(){
        const resp = await fetch("/link/{{session_id}}");
        if(resp.status === 200){
            const data = await resp.json();
            window.location.href = data.url;
        } else {
            setTimeout(checkLicense, 3000); // Reintenta cada 3s
        }
    }
    checkLicense();
    </script>
    """, session_id=session_id)

# ---------------- LINK POR SESSION ----------------
@app.route("/link/<session_id>")
def link(session_id):
    link_id = get_license_by_session(session_id)
    if not link_id:
        return "Licencia aún no lista", 404
    return jsonify({"url": f"{BASE_URL}/viewer/{link_id}"})

# ---------------- WEBHOOK STRIPE ----------------
@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        return "Webhook inválido", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session["id"]
        line_items = stripe.checkout.Session.list_line_items(session_id)
        price_id = line_items.data[0].price.id
        dias = 10
        for p in PLANES.values():
            if p["price_id"] == price_id:
                dias = p["dias"]
        link_id = str(uuid.uuid4())[:8]
        expira = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        create_license(link_id, session_id, expira)
        print(f"✅ LICENCIA CREADA: {link_id}")
    return "OK", 200

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
