import os, uuid, time, stripe
from flask import Flask, request, jsonify, redirect, render_template_string
from datetime import datetime, timedelta
from database import init_db, create_license, get_license_by_link, get_license_by_session, set_active_device

app = Flask(__name__, static_url_path='/static', static_folder='static')
init_db()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"
stripe.api_key = STRIPE_SECRET_KEY

PLANES = {
    "price_1Sv5uXBOA5mT4t0PtV7RaYCa": [15.00, 10, "Plan 10 Días"],
    "price_1Sv69jBOA5mT4t0PUA7yiisS": [25.00, 28, "Plan 28 Días"],
    "price_1Sv6H2BOA5mT4t0PppizlRAK": [0.00, 20, "Prueba Admin ($0.00)"]
}

PRUEBA_LINK_ID = "PRUEBA123"  # Tu licencia de prueba interna

VIEWER_HTML = """[MANTENER EL HTML DEL VISOR TAL COMO LO TENÍAS]"""

@app.route("/")
def home():
    html = '<div style="max-width:400px; margin:auto; text-align:center; font-family:sans-serif; background:#000; color:white; padding:40px; border-radius:20px; border: 2px solid #0056b3;">'
    html += '<h1>AL CIELO</h1><p>MAY ROGA LLC</p><hr>'
    for pid, (p, d, n) in PLANES.items():
        html += f'<a href="/checkout/{pid}" style="display:block; background:#0056b3; color:white; padding:18px; margin:15px 0; text-decoration:none; border-radius:12px; font-weight:bold;">{n} - ${p}</a>'
    html += '</div>'
    return html

@app.route("/checkout/<pid>")
def checkout(pid):
    if pid == "price_1Sv6H2BOA5mT4t0PppizlRAK":
        lid = PRUEBA_LINK_ID
        create_license(lid, f"ADMIN_{lid}", (datetime.utcnow() + timedelta(days=28)).strftime("%Y-%m-%d %H:%M:%S"))
        return redirect(f"/activar/{lid}")
    session = stripe.checkout.Session.create(
        payment_method_types=["card"], mode="payment",
        line_items=[{"price": pid, "quantity": 1}],
        success_url=f"{BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=BASE_URL
    )
    return redirect(session.url)

@app.route("/success")
def success():
    time.sleep(8)
    return redirect(f"/link/{request.args.get('session_id')}")

@app.route("/link/<session_id>")
def link_redirect(session_id):
    lid = get_license_by_session(session_id)
    return redirect(f"/activar/{lid}") if lid else ("Confirmando...", 404)

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    lic = get_license_by_link(link_id)
    if not lic:
        # Crear licencia si es prueba
        if link_id == PRUEBA_LINK_ID:
            create_license(PRUEBA_LINK_ID, f"ADMIN_{PRUEBA_LINK_ID}", (datetime.utcnow() + timedelta(days=28)).strftime("%Y-%m-%d %H:%M:%S"))
            lic = get_license_by_link(PRUEBA_LINK_ID)
        else:
            return jsonify({"error":"Licencia no encontrada"}), 404

    if request.method == "POST":
        device_id = request.json.get("device_id")
        legal_ok = request.json.get("legal_ok", False)

        # Excepción para licencia de prueba
        if link_id == PRUEBA_LINK_ID:
            # Permitir hasta 3 dispositivos
            conn = set_active_device(link_id, device_id)  # Reutiliza función, modificar si excede 3
            return jsonify({"status":"OK","map_url":"/viewer/"+link_id})

        # Para usuarios normales, exigir legal_ok
        if not legal_ok:
            return jsonify({"error":"Consentimiento legal requerido"}), 403

        set_active_device(link_id, device_id)
        return jsonify({"status":"OK","map_url":"/viewer/"+link_id})

    return render_template_string("""
    <body style='background:#000; color:white; text-align:center; padding-top:100px;'>
    <h2>AL CIELO BY MAY ROGA LLC</h2>
    <button style='padding:20px; background:#0056b3; color:white; border:none; border-radius:10px; font-size:20px;' onclick='act()'>ACEPTAR Y ENTRAR AL SISTEMA</button>
    <script>
    function act(){
        fetch('',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({device_id:crypto.randomUUID(), legal_ok:true})
        }).then(r=>r.json()).then(d=>window.location.href=d.map_url)
    }
    </script>
    </body>
    """)

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "DENEGADO", 403
    return render_template_string(VIEWER_HTML, expira=lic[1])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
