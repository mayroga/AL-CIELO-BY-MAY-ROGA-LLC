import os, uuid, time, stripe
from flask import Flask, request, jsonify, redirect, render_template_string
from datetime import datetime, timedelta
from database import init_db, create_license, get_license_by_link, get_license_by_session, set_active_device

# ======================================================
# APP
# ======================================================
app = Flask(__name__, static_url_path='/static', static_folder='static')
init_db()

# ======================================================
# CONFIGURACIÓN
# ======================================================
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"
stripe.api_key = STRIPE_SECRET_KEY

PLANES = {
    "price_1Sv5uXBOA5mT4t0PtV7RaYCa": [15.00, 10, "Plan 10 Días"],
    "price_1Sv69jBOA5mT4t0PUA7yiisS": [25.00, 28, "Plan 28 Días"],
    "price_1Sv6H2BOA5mT4t0PppizlRAK": [0.00, 20, "Prueba Admin ($0.00)"]
}

# ======================================================
# VISOR OFFLINE
# ======================================================
VIEWER_HTML = open("viewer.html", encoding="utf-8").read()

# ======================================================
# RUTAS
# ======================================================
@app.route("/")
def home():
    html = """
    <div style="max-width:420px;margin:auto;text-align:center;
    font-family:sans-serif;background:#000;color:white;
    padding:40px;border-radius:20px;border:2px solid #0056b3;">
    <h1>AL CIELO</h1>
    <p>BY MAY ROGA LLC</p>
    <hr>
    """
    for pid, (precio, dias, nombre) in PLANES.items():
        html += f"""
        <a href="/checkout/{pid}"
        style="display:block;background:#0056b3;color:white;
        padding:18px;margin:15px 0;text-decoration:none;
        border-radius:12px;font-weight:bold;">
        {nombre} – ${precio}
        </a>
        """
    html += "</div>"
    return html

@app.route("/checkout/<pid>")
def checkout(pid):
    if pid == "price_1Sv6H2BOA5mT4t0PppizlRAK":
        lid = str(uuid.uuid4())[:8]
        create_license(
            lid,
            f"ADMIN_{lid}",
            (datetime.utcnow() + timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
        )
        return redirect(f"/activar/{lid}")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[{"price": pid, "quantity": 1}],
        success_url=f"{BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=BASE_URL
    )
    return redirect(session.url)

@app.route("/success")
def success():
    time.sleep(5)
    return redirect(f"/link/{request.args.get('session_id')}")

@app.route("/link/<session_id>")
def link_redirect(session_id):
    lid = get_license_by_session(session_id)
    return redirect(f"/activar/{lid}") if lid else ("Confirmando...", 404)

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    if request.method == "POST":
        if not request.json.get("legal_ok"):
            return jsonify({"error": "Consentimiento legal requerido"}), 403

        device_id = request.json.get("device_id")
        try:
            memoria = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024 ** 3)
        except:
            memoria = 1.0
        if memoria < 0.5:
            return jsonify({"error": "Dispositivo con memoria insuficiente para navegación offline"}), 403

        set_active_device(link_id, device_id)
        return jsonify({"status": "OK", "map_url": f"/viewer/{link_id}"})

    return render_template_string(open("index.html", encoding="utf-8").read())

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic:
        return "DENEGADO", 403
    return render_template_string(VIEWER_HTML)

# ======================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
