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

app = Flask(__name__, static_url_path='/static', static_folder='static')
init_db()

# ================= ENV =================
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"
TILESERVER_URL = "https://al-cielo-by-may-roga-llc.onrender.com:8080"  # PMTiles TileServer URL

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
        html += f'<li><a href="https://buy.stripe.com/{price_id}" target="_blank">{desc} – ${precio} / {dias} días</a></li>'
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
        line_items = stripe.checkout.Session.list_line_items(session_id)
        price_id = line_items.data[0].price.id
        dias = PLANES.get(price_id, [0, 10])[1]

        link_id = str(uuid.uuid4())[:8]
        expira = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        create_license(link_id, session_id, expira)
        print(f"✅ LICENCIA CREADA: {link_id} – Price ID: {price_id}")

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

    _, expira, active_device = lic

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
            "map_url": f"{BASE_URL}/mapa/{link_id}"
        })

    return render_template_string("""
    <h2>AL CIELO – Activación</h2>
    <p>Licencia válida hasta: {{expira}}</p>
    <p>Máx. 2 dispositivos · Solo 1 activo</p>
    <p><b>Blindaje legal:</b> Uso exclusivo del mapa en streaming, sin descarga. Redistribución prohibida.</p>
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
        window.location.href = data.map_url;
      } else {
        alert(data.error);
      }
    }
    </script>
    """, expira=expira)

# ================= MAPA STREAMING =================
@app.route("/mapa/<link_id>")
def mapa(link_id):
    lic = get_license_by_link(link_id)
    if not lic:
        return "Acceso no autorizado", 403

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>AL CIELO – Mapa Cuba</title>
  <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet"/>
  <style>
    html, body, #map { margin:0; padding:0; width:100%; height:100vh; }
  </style>
</head>
<body>
<div id="map"></div>
<script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
<script>
const map = new maplibregl.Map({
    container: "map",
    style: {
        version: 8,
        sources: {
            cuba: {
                type: "raster",
                tiles: ["{{tiles_url}}/tiles/{z}/{x}/{y}.png"],
                tileSize: 256
            }
        },
        layers: [{
            id: "cuba",
            type: "raster",
            source: "cuba"
        }]
    },
    center: [-79.5, 21.5],
    zoom: 6
});

// Navegación por voz básica
function speak(text){ 
    const msg = new SpeechSynthesisUtterance(text);
    msg.lang = 'es-ES';
    window.speechSynthesis.speak(msg);
}

// Ejemplo de recalculo (mock)
map.on('moveend', () => {
    // Aquí podrías calcular si el usuario se desvió y dar aviso
    // speak("Recalculando ruta...");
});
</script>
</body>
</html>
""", tiles_url=TILESERVER_URL)

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
