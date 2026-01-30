import os, uuid, time, stripe
from flask import Flask, request, jsonify, redirect, render_template_string
from datetime import datetime, timedelta
from database import init_db, create_license, get_license_by_link, get_license_by_session, set_active_device

app = Flask(__name__, static_url_path='/static', static_folder='static')
init_db()

# CONFIGURACIÓN DE SEGURIDAD - MAY ROGA LLC
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"
stripe.api_key = STRIPE_SECRET_KEY

PLANES = {
    "price_1Sv5uXBOA5mT4t0PtV7RaYCa": [15.00, 10, "Plan 10 Días"],
    "price_1Sv69jBOA5mT4t0PUA7yiisS": [25.00, 28, "Plan 28 Días"],
    "price_1Sv6H2BOA5mT4t0PppizlRAK": [0.00, 20, "Prueba Admin ($0.00)"]
}

VIEWER_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <title>AL CIELO - Sistema de Navegación Profesional</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css" />
    <style>
        body { margin:0; background:#000; font-family: 'Segoe UI', sans-serif; color:white; overflow:hidden; }
        #map { height: 75vh; width: 100%; border-bottom: 3px solid #0056b3; }
        .panel { height: 25vh; background:#111; padding:15px; display:flex; flex-direction:column; gap:10px; }
        .search-box { display:flex; gap:8px; }
        input { flex:1; padding:12px; border-radius:8px; border:1px solid #333; background:#222; color:white; font-size:16px; }
        .btn-nav { background:#0056b3; color:white; border:none; padding:12px; border-radius:8px; font-weight:bold; cursor:pointer; width:100%; }
        .status-bar { font-size:11px; color:#666; display:flex; justify-content:space-between; }
        #instrucciones { font-size:14px; color:#00ff00; font-weight:bold; text-align:center; min-height:1.2em; }
        .leaflet-routing-container { display: none; } /* Ocultamos el panel de texto para usar nuestra voz */
    </style>
</head>
<body oncontextmenu="return false;">
    <div id="map"></div>
    <div class="panel">
        <div id="instrucciones">Listo para navegar Cuba</div>
        <div class="search-box">
            <input id="origen" placeholder="Inicio (Ej: Lawton, Habana)">
            <input id="destino" placeholder="Destino (Ej: Varadero)">
        </div>
        <button class="btn-nav" onclick="iniciarNavegacion()">INICIAR RUTA AL CIELO</button>
        <div class="status-bar">
            <span>MAY ROGA LLC - JURISDICCIÓN USA</span>
            <span>EXPIRA: {{expira}}</span>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    <script>
        // SEGURIDAD: BOMBA DE TIEMPO
        const expira = new Date("{{expira}}");
        if (new Date() > expira) {
            alert("LICENCIA EXPIRADA - Borrando datos por seguridad legal.");
            localStorage.clear();
            window.location.href = "/";
        }

        var map = L.map('map', { zoomControl: false }).setView([21.5, -79.5], 7);
        
        // Capa Híbrida Blindada
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: 'AL CIELO by May Roga LLC'
        }).addTo(map);

        var control = L.Routing.control({
            waypoints: [],
            router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1' }),
            lineOptions: { styles: [{color: '#00ff00', opacity: 0.9, weight: 8}] },
            language: 'es',
            addWaypoints: false
        }).addTo(map);

        // NAVEGACIÓN POR VOZ PASO A PASO
        control.on('routesfound', function(e) {
            var instructions = e.routes[0].instructions;
            narrarPasos(instructions);
        });

        async function geocode(query) {
            const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${query},Cuba`);
            const d = await r.json();
            return d.length > 0 ? L.latLng(d[0].lat, d[0].lon) : null;
        }

        async function iniciarNavegacion() {
            const p1 = await geocode(document.getElementById('origen').value);
            const p2 = await geocode(document.getElementById('destino').value);
            
            if(p1 && p2) {
                control.setWaypoints([p1, p2]);
                map.flyTo(p1, 15);
                hablar("Iniciando traslado. Siga la línea verde en pantalla.");
            } else {
                alert("Error: Verifique las direcciones en Cuba.");
            }
        }

        function narrarPasos(pasos) {
            let i = 0;
            function siguiente() {
                if (i < pasos.length) {
                    document.getElementById('instrucciones').innerText = pasos[i].text;
                    hablar(pasos[i].text);
                    i++;
                    setTimeout(siguiente, 8000); // Intervalo de descripción
                }
            }
            siguiente();
        }

        function hablar(texto) {
            const u = new SpeechSynthesisUtterance(texto);
            u.lang = 'es-US';
            u.rate = 0.9;
            window.speechSynthesis.speak(u);
        }

        // ANTI-COPIA
        window.addEventListener('keydown', e => {
            if(e.ctrlKey && (e.key==='s' || e.key==='u' || e.key==='p')) e.preventDefault();
        });
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    html = '<div style="max-width:400px; margin:auto; text-align:center; font-family:sans-serif; background:#000; color:white; padding:40px; border-radius:20px;">'
    html += '<h2>AL CIELO</h2><p>May Roga LLC</p><hr>'
    for pid, (p, d, n) in PLANES.items():
        color = "#0056b3" if p > 0 else "#333"
        html += f'<a href="/checkout/{pid}" style="display:block; background:{color}; color:white; padding:15px; margin:10px 0; text-decoration:none; border-radius:10px; font-weight:bold;">{n} - ${p}</a>'
    html += '<p style="font-size:10px; color:#555;">Sistema de Traslado Terrestre Cuba</p></div>'
    return html

@app.route("/checkout/<price_id>")
def checkout(price_id):
    if price_id == "price_1Sv6H2BOA5mT4t0PppizlRAK":
        lid = str(uuid.uuid4())[:8]
        exp = (datetime.utcnow() + timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
        create_license(lid, f"ADMIN_{lid}", exp)
        return redirect(f"/activar/{lid}")
    
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
    time.sleep(10)
    return redirect(f"/link/{request.args.get('session_id')}")

@app.route("/link/<session_id>")
def link_redirect(session_id):
    lid = get_license_by_session(session_id)
    return redirect(f"/activar/{lid}") if lid else ("Procesando...", 404)

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Enlace Inválido", 404
    if request.method == "POST":
        set_active_device(link_id, request.json.get("device_id"))
        return jsonify({"status": "OK", "map_url": f"/viewer/{link_id}"})
    return render_template_string("<h3>Términos May Roga LLC</h3><button onclick='act()'>ACEPTAR Y ENTRAR AL SISTEMA</button><script>function act(){ fetch('',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:crypto.randomUUID()})}).then(r=>r.json()).then(d=>window.location.href=d.map_url)}</script>")

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "Acceso Denegado", 403
    return render_template_string(VIEWER_HTML, expira=lic[1])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
