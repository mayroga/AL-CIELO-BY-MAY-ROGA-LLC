import os
import uuid
import stripe
from flask import Flask, redirect, request, jsonify, render_template_string
from datetime import datetime, timedelta

from database import (
    init_db,
    create_license,
    get_license_by_session,
    get_license_by_link
)

app = Flask(__name__, static_folder="static")
init_db()

# ================== STRIPE ==================
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"

# ================== PLANES ==================
PLANES = {
    "10dias": {
        "price_id": "price_1Sv5uXBOA5mT4t0PtV7RaYCa",
        "precio": "$15",
        "dias": 10,
        "nombre": "Asesoría 10 Días"
    },
    "28dias": {
        "price_id": "price_1Sv69jBOA5mT4t0PUA7yiisS",
        "precio": "$25",
        "dias": 28,
        "nombre": "Asesoría 28 Días"
    },
    "admin": {
        "price_id": "price_1Sv6H2BOA5mT4t0PppizlRAK",
        "precio": "$0",
        "dias": 20,
        "nombre": "Acceso Admin"
    }
}

# ================== HOME ==================
@app.route("/")
def home():
    html = "<h2>AL CIELO by May Roga LLC</h2><ul>"
    for k, p in PLANES.items():
        html += f"""
        <li>
            <b>{p['nombre']}</b> – {p['precio']} / {p['dias']} días<br>
            <a href="/checkout/{k}">Comprar</a>
        </li><br>
        """
    html += "</ul>"
    return html

# ================== CHECKOUT ==================
@app.route("/checkout/<plan>")
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

# ================== SUCCESS ==================
@app.route("/success")
def success():
    session_id = request.args.get("session_id")
    if not session_id:
        return "Sesión inválida", 400

    if get_license_by_session(session_id):
        lic = get_license_by_session(session_id)
        return redirect(f"/activar/{lic}")

    session = stripe.checkout.Session.retrieve(session_id)
    price_id = stripe.checkout.Session.list_line_items(session_id).data[0].price.id

    dias = next(p["dias"] for p in PLANES.values() if p["price_id"] == price_id)

    licencia = uuid.uuid4().hex[:8]
    expira = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")

    create_license(licencia, session_id, expira)

    return redirect(f"/activar/{licencia}")

# ================== ACTIVAR ==================
@app.route("/activar/<licencia>")
def activar(licencia):
    lic = get_license_by_link(licencia)
    if not lic:
        return "Licencia inválida o vencida", 404

    return f"""
    <h2>Licencia activada</h2>
    <p>Válida hasta: {lic[1]}</p>
    <a href="/static/maps/cuba_full.mbtiles">Descargar mapa</a>
    """

# ================== RUN ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
