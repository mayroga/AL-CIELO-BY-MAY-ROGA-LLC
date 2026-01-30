import os, uuid, time, stripe
from flask import Flask, request, jsonify, redirect, render_template_string
from datetime import datetime, timedelta
from database import init_db, create_license, get_license_by_link, get_license_by_session, set_active_device

app = Flask(__name__)
init_db()

# Configuración de May Roga LLC
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"
stripe.api_key = STRIPE_SECRET_KEY

VIEWER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>AL CIELO - Navegación</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css" />
    <style>
        body { margin:0; background:#000; font-family:sans-serif; color:white; }
        #map { height: 75vh; width: 100%; }
        .ui { height: 25vh; background:#111; padding:10px; display:flex; flex-direction:column; gap:8px; }
        .row { display:flex; gap:5px; }
        input { flex:1; padding:10px; border-radius:5px; border:none; background:#222; color:white; font-size:12px; }
        button { padding:10px; border-radius:5px; border:none; font-weight:bold; cursor:pointer; }
        .btn-go { background:#28a745; color:white; flex:1; }
        .btn-del { background:#dc3545; color:white; font-size:10px; }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="ui">
        <div class="row">
            <input id="start" placeholder="Inicio (Ej: Lawton, Habana)">
            <input id="end" placeholder="Destino (Ej: Varadero)">
        </div>
        <div class="row">
            <button class="btn-go" onclick="calcularRuta()">ESTABLECER RUTA DE ASESORÍA</button>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <button class="btn-del" onclick="borrar()">BORRAR RASTRO</button>
            <small style="color:#666;">Expira: {{expira}}</small>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    <script>
        var map = L.map('map').setView([23.1136, -82.3666], 12);
        
        // Capa Híbrida: Busca local, si falla usa satélite/osm
        var localLayer = L.tileLayer('/static/maps/cuba_tiles/{z}/{x}/{y}.png', { maxZoom: 18 });
        var osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

        var control = L.Routing.control({
            waypoints: [],
            routeWhileDragging: true,
            lineOptions: { styles: [{color: '#00ff00', opacity: 0.8, weight: 6}] },
            createMarker: function() { return null; } // Limpieza visual
        }).addTo(map);

        async function geocode(addr) {
            const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${addr},Cuba`);
            const data = await res.json();
            return data.length > 0 ? L.latLng(data[0].lat, data[0].lon) : null;
        }

        async function calcularRuta() {
            const sAddr = document.getElementById('start').value;
            const eAddr = document.getElementById('end').value;
            
            if(!sAddr || !eAddr) { alert("Indique Inicio y Destino"); return; }
            
            const p1 = await geocode(sAddr);
            const p2 = await geocode(eAddr);
            
            if(p1 && p2) {
                control.setWaypoints([p1, p2]);
                map.fitBounds([p1, p2]);
                hablar("Ruta calculada de " + sAddr + " hacia " + eAddr);
            } else {
                alert("No se encontraron las ubicaciones. Intente ser más específico.");
            }
        }

        function hablar(t) {
            var m = new SpeechSynthesisUtterance(t);
            m.lang = 'es-US';
            window.speechSynthesis.speak(m);
        }

        function borrar() {
            if(confirm("¿Borrar historial de navegación?")) {
                localStorage.clear();
                window.location.href = "/";
            }
        }
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return f"""
    <body style="text-align:center; padding:50px; font-family:sans-serif; background:#f4f4f4;">
        <h1>AL CIELO</h1>
        <div style="margin:20px;"><a href="/checkout/price_15" style="display:block; padding:20px; background:blue; color:white; text-decoration:none; border-radius:10px;">10 Días - $15.00</a></div>
        <div style="margin:20px;"><a href="/checkout/price_25" style="display:block; padding:20px; background:green; color:white; text-decoration:none; border-radius:10px;">28 Días - $25.00</a></div>
        <p>May Roga LLC - Asesoría de Carga y Navegación</p>
    </body>
    """

@app.route("/checkout/<pid>")
def checkout(pid):
    # Lógica de Stripe simplificada para el ejemplo
    link_id = str(uuid.uuid4())[:8]
    exp = (datetime.utcnow() + timedelta(days=10 if "15" in pid else 28)).strftime("%Y-%m-%d")
    create_license(link_id, f"PAY_{link_id}", exp)
    return redirect(f"/activar/{link_id}")

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    if request.method == "POST":
        set_active_device(link_id, request.json.get("device_id"))
        return jsonify({"map_url": f"/viewer/{link_id}"})
    return render_template_string("<h2>Acepto Términos May Roga LLC</h2><button onclick='act()'>Activar</button><script>function act(){ fetch('',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:crypto.randomUUID()})}).then(r=>r.json()).then(d=>window.location.href=d.map_url)}</script>")

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    return render_template_string(VIEWER_HTML, expira=lic[1])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
