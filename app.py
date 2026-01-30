import os
import uuid
import time
import stripe
from flask import Flask, request, jsonify, redirect, render_template_string
from datetime import datetime, timedelta
from database import init_db, create_license, get_license_by_link, get_license_by_session, set_active_device

app = Flask(__name__, static_url_path='/static', static_folder='static')

# Inicializar Base de Datos al arrancar
init_db()

# Configuración de Seguridad y Pagos
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"

stripe.api_key = STRIPE_SECRET_KEY

# ESTRUCTURA DE PRECIOS OBLIGATORIA
PLANES = {
    "price_admin_000": [0.00, 20, "Prueba Admin (Costo $0.00)"],
    "price_10_days_15": [15.00, 10, "Asesoría 10 Días - $15.00"],
    "price_28_days_25": [25.00, 28, "Asesoría 28 Días - $25.00"]
}

# --- PLANTILLAS HTML INTEGRADAS ---

HTML_ACTIVACION = """
<div style="font-family:sans-serif; max-width:600px; margin:50px auto; padding:30px; border:2px solid #0059b3; border-radius:15px; text-align:center;">
    <h2 style="color:#0059b3;">AL CIELO – TÉRMINOS Y CONDICIONES</h2>
    <div style="text-align:left; background:#f9f9f9; padding:15px; border-radius:10px; font-size:14px;">
        <p>Declaro bajo mi responsabilidad que soy <b>ciudadano o residente legal en los Estados Unidos</b> y que cumpliré con todas las leyes aplicables de la OFAC y el Departamento de Estado.</p>
        <p><b>Control de Licencia:</b> Esta asesoría permite el uso en 2 dispositivos, pero solo 1 activo a la vez. Si activa este teléfono, el anterior perderá la conexión.</p>
        <p><b>Privacidad:</b> May Roga LLC no almacena su ubicación. El botón "BORRAR" elimina todo rastro local.</p>
    </div>
    <br>
    <label style="display:block; margin-bottom:20px;">
        <input type="checkbox" id="check-legal"> He leído y acepto el blindaje legal de May Roga LLC.
    </label>
    <button onclick="activarServicio()" style="width:100%; padding:20px; background:#28a745; color:white; border:none; border-radius:10px; font-weight:bold; cursor:pointer;">ACTIVAR SERVICIO AHORA</button>
</div>
<script>
async function activarServicio() {
    if(!document.getElementById('check-legal').checked) {
        alert("Debe aceptar los términos legales para continuar.");
        return;
    }
    const device_id = localStorage.getItem("device_id") || crypto.randomUUID();
    localStorage.setItem("device_id", device_id);
    const link_id = window.location.pathname.split("/").pop();

    const res = await fetch(`/activar/${link_id}`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ device_id: device_id, legal_ok: true })
    });
    const data = await res.json();
    if(res.ok) {
        window.location.href = data.map_url;
    } else {
        alert(data.error || "Error de activación");
    }
}
</script>
"""

VIEWER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>AL CIELO - Navegación Live</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <style>
        body { margin:0; padding:0; background:#000; font-family:sans-serif; }
        #map { height: 80vh; width: 100%; }
        .ui { height: 20vh; background:#1a1a1a; color:white; padding:15px; display:flex; flex-direction:column; justify-content:space-around; }
        .nav-btn { background:#007bff; color:white; border:none; padding:15px; border-radius:8px; font-weight:bold; }
        .del-btn { background:#dc3545; color:white; border:none; padding:8px; border-radius:5px; font-size:12px; margin-top:5px;}
        input { padding:12px; border-radius:5px; border:none; background:#333; color:white; }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="ui">
        <div style="display:flex; gap:10px;">
            <input id="coord" style="flex-grow:1;" placeholder="Lat, Lon (Opcional)">
            <button class="nav-btn" onclick="iniciarNav()">NAVEGAR</button>
        </div>
        <button class="del-btn" onclick="borrarDatos()">BORRAR TODO Y CERRAR SESIÓN</button>
        <div style="font-size:10px; color:#aaa; text-align:center;">Expira: {{expira}} | AL CIELO by May Roga LLC</div>
    </div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        var map = L.map('map').setView([23.1136, -82.3666], 10);
        
        // MOTOR OFFLINE: Lee las carpetas extraídas del MBTILES
        L.tileLayer('/static/maps/cuba_tiles/{z}/{x}/{y}.png', {
            maxZoom: 18, minZoom: 6, tms: true, attribution: 'May Roga LLC'
        }).addTo(map);

        function hablar(t) {
            var m = new SpeechSynthesisUtterance(t);
            m.lang = 'es-US';
            window.speechSynthesis.speak(m);
        }

        function iniciarNav() {
            map.locate({setView: true, watch: true, enableHighAccuracy: true});
            hablar("Iniciando Asesoría de Navegación Al Cielo.");
        }

        map.on('locationfound', function(e) {
            L.marker(e.latlng).addTo(map).bindPopup("Su ubicación").openPopup();
        });

        function borrarDatos() {
            if(confirm("¿Desea borrar la sesión? Esto cerrará el acceso en este equipo.")) {
                localStorage.clear();
                window.location.href = "/";
            }
        }
    </script>
</body>
</html>
"""

# --- RUTAS DE LA APLICACIÓN ---

@app.route("/")
def home():
    html = "<body style='text-align:center; padding:50px; font-family:sans-serif;'>"
    html += "<h1>AL CIELO</h1><h3>Asesoría de Navegación para Cuba</h3>"
    for p_id, (precio, dias, desc) in PLANES.items():
        html += f'<div style="margin:20px;"><a href="/checkout/{p_id}" style="padding:15px 40px; background:#0059b3; color:white; text-decoration:none; border-radius:10px; font-size:18px; display:inline-block;">{desc}</a></div>'
    return html + "</body>"

@app.route("/checkout/<price_id>")
def checkout(price_id):
    if price_id not in PLANES: return "Plan inválido", 404
    
    # Bypass para el link de Prueba Admin ($0.00)
    if price_id == "price_admin_000":
        link_id = str(uuid.uuid4())[:8]
        expira = (datetime.utcnow() + timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
        create_license(link_id, f"ADMIN_{link_id}", expira)
        return redirect(f"/activar/{link_id}")

    # Pago real con Stripe
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=BASE_URL
    )
    return redirect(session.url)

@app.route("/success")
def success():
    session_id = request.args.get("session_id")
    time.sleep(5) # Tiempo para que el webhook procese
    return redirect(f"/link/{session_id}")

@app.route("/link/<session_id>")
def link_redirect(session_id):
    link_id = get_license_by_session(session_id)
    if not link_id: return "Confirmando pago... Refresque en 5 segundos.", 404
    return redirect(f"/activar/{link_id}")

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Licencia inválida", 404
    
    if request.method == "POST":
        device_id = request.json.get("device_id")
        set_active_device(link_id, device_id)
        return jsonify({"status": "OK", "map_url": f"/viewer/{link_id}"})
    
    return render_template_string(HTML_ACTIVACION)

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Acceso Denegado", 403
    return render_template_string(VIEWER_HTML, link_id=link_id, expira=lic[1])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
