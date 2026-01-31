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

VIEWER_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <title>AL CIELO - Navegación de Precisión</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <style>
        body { margin:0; background:#000; font-family: 'Segoe UI', sans-serif; color:white; overflow:hidden; }
        #map { height: 55vh; width: 100%; border-bottom: 3px solid #0056b3; }
        .panel { height: 45vh; background:#111; padding:8px; display:flex; flex-direction:column; gap:4px; overflow-y: auto; }
        .telemetria { display: flex; justify-content: space-around; background: #222; padding: 6px; border-radius: 8px; border: 1px solid #0af; color: #0af; font-family: monospace; font-size: 14px; }
        .search-box { display:flex; flex-direction:column; gap:4px; }
        input { padding:12px; border-radius:6px; border:1px solid #333; background:#222; color:white; font-size:16px; width: 93%; }
        .btn-group { display: flex; gap: 4px; }
        .btn-nav { flex: 2; background:#0056b3; color:white; border:none; padding:15px; border-radius:6px; font-weight:bold; cursor:pointer; font-size:16px; }
        .btn-reset { flex: 1; background:#cc0000; color:white; border:none; padding:15px; border-radius:6px; font-weight:bold; cursor:pointer; font-size:14px; }
        .btn-extra { background:#333; color:#fff; border:1px solid #555; padding:10px; border-radius:6px; font-size:12px; flex:1; font-weight: bold; }
        #instrucciones { font-size:18px; color:#00ff00; font-weight:bold; text-align:center; min-height:1.5em; background: rgba(0,0,0,0.8); padding: 5px; border-radius: 5px; }
        .car-icon { filter: drop-shadow(0 0 10px #fff); z-index: 1000 !important; font-size: 50px; text-align: center; }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="panel">
        <div id="instrucciones">ESPERANDO DESTINO EN CUBA...</div>
        <div class="telemetria">
            <div>VEL: <b id="vel" style="font-size:20px;">0</b> km/h</div>
            <div>DIST: <b id="dist" style="font-size:20px;">0.0</b> km</div>
            <div id="status">GPS: LISTO</div>
        </div>
        <div class="search-box">
            <input id="origen" placeholder="Origen (Ej: Aeropuerto Habana)">
            <input id="destino" placeholder="Destino (Ej: Hotel Varadero)">
        </div>
        <div class="btn-group">
            <button class="btn-nav" onclick="iniciarNavegacion()">INICIAR RUTA SEGURA</button>
            <button class="btn-reset" onclick="reiniciar()">REINICIAR</button>
        </div>
        <div class="btn-group">
            <button class="btn-extra" onclick="buscarCercano('restaurant')">🍴 COMIDA</button>
            <button class="btn-extra" onclick="buscarCercano('hotel')">🛌 DESCANSO</button>
            <button class="btn-extra" onclick="buscarCercano('fuel')">⛽ GASOLINA</button>
            <button class="btn-extra" onclick="buscarCercano('shop')">📦 MYPIME</button>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    <script>
        var map = L.map('map', { zoomControl: false }).setView([23.1136, -82.3666], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

        var carMarker = L.marker([23.1136, -82.3666], {
            icon: L.divIcon({html: '🚗', className: 'car-icon', iconSize: [60, 60]})
        }).addTo(map);

        var control = L.Routing.control({
            waypoints: [],
            router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1', profile: 'car' }),
            lineOptions: { styles: [{color: '#00ff00', opacity: 1, weight: 12}] },
            showAlternatives: true,
            language: 'es',
            createMarker: function() { return null; }
        }).addTo(map);

        async function buscarLugar(q) {
            const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${q},Cuba&limit=1`);
            const d = await r.json();
            return d.length > 0 ? L.latLng(d[0].lat, d[0].lon) : null;
        }

        async function iniciarNavegacion() {
            const p1 = await buscarLugar(document.getElementById('origen').value);
            const p2 = await buscarLugar(document.getElementById('destino').value);
            if(p1 && p2) {
                control.setWaypoints([p1, p2]);
                hablar("Ruta configurada. Iniciando monitoreo de seguridad.");
                activarSeguimientoReal();
            }
        }

        function activarSeguimientoReal() {
            navigator.geolocation.watchPosition(pos => {
                const latlng = [pos.coords.latitude, pos.coords.longitude];
                const vel = pos.coords.speed ? Math.round(pos.coords.speed * 3.6) : 0;
                document.getElementById('vel').innerText = vel;
                carMarker.setLatLng(latlng);
                map.setView(latlng, 18);
                
                // Bloquear calles laterales con parches pequeños para no estorbar el carro
                obstruirLaterales(latlng);
            }, null, { enableHighAccuracy: true });
        }

        function obstruirLaterales(pos) {
            // Genera parches rojos en las intersecciones para indicar "No Salir de la Ruta"
            const dist = 0.0008; 
            const puntos = [[pos[0]+dist, pos[1]], [pos[0]-dist, pos[1]], [pos[0], pos[1]+dist], [pos[0], pos[1]-dist]];
            puntos.forEach(p => {
                let r = L.circle(p, {color: 'red', fillColor: '#f03', fillOpacity: 0.6, radius: 15}).addTo(map);
                setTimeout(() => map.removeLayer(r), 2500);
            });
        }

        control.on('routesfound', function(e) {
            const route = e.routes[0];
            document.getElementById('dist').innerText = (route.summary.totalDistance / 1000).toFixed(1);
            
            // Sistema de Voz Anticipada para Seguridad del Chofer
            route.instructions.forEach((inst, i) => {
                setTimeout(() => {
                    document.getElementById('instrucciones').innerText = inst.text;
                    hablar("Atención chofer: " + inst.text);
                }, i * 10000); // Intervalo simulado de avance
            });
        });

        async function buscarCercano(tipo) {
            const p = carMarker.getLatLng();
            const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${tipo}&lat=${p.lat}&lon=${p.lng}&zoom=15`);
            const d = await r.json();
            d.forEach(l => {
                L.marker([l.lat, l.lon], {icon: L.divIcon({html:'📍', className:'loc'})}).addTo(map).bindPopup(l.display_name).openPopup();
            });
            hablar("Buscando " + tipo + " en los alrededores.");
        }

        function reiniciar() {
            control.setWaypoints([]);
            document.getElementById('origen').value = "";
            document.getElementById('destino').value = "";
            document.getElementById('instrucciones').innerText = "ESPERANDO NUEVA RUTA...";
            hablar("Sistema reiniciado. Puede ingresar un nuevo destino.");
        }

        function hablar(t) {
            const u = new SpeechSynthesisUtterance(t);
            u.lang = 'es-ES'; u.rate = 0.85;
            window.speechSynthesis.speak(u);
        }
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    html = '<div style="max-width:400px; margin:auto; text-align:center; font-family:sans-serif; background:#000; color:white; padding:40px; border-radius:20px; border: 2px solid #0056b3;">'
    html += '<h1 style="color:#0af;">AL CIELO</h1><p>MAY ROGA LLC</p><hr>'
    for pid, (p, d, n) in PLANES.items():
        html += f'<a href="/checkout/{pid}" style="display:block; background:#0056b3; color:white; padding:18px; margin:15px 0; text-decoration:none; border-radius:12px; font-weight:bold; font-size:18px;">{n} - ${p}</a>'
    html += '</div>'
    return html

@app.route("/checkout/<pid>")
def checkout(pid):
    if pid == "price_1Sv6H2BOA5mT4t0PppizlRAK":
        lid = str(uuid.uuid4())[:8]
        create_license(lid, f"ADMIN_{lid}", (datetime.utcnow() + timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"))
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
    return redirect(f"/activar/{lid}") if lid else ("Error de enlace", 404)

@app.route("/activar/<link_id>", methods=["GET", "POST"])
def activar(link_id):
    if request.method == "POST":
        set_active_device(link_id, request.json.get("device_id"))
        return jsonify({"status": "OK", "map_url": f"/viewer/{link_id}"})
    return render_template_string("<body style='background:#000; color:white; text-align:center; padding-top:100px;'><h2>MAY ROGA LLC - CONTRATO</h2><button style='padding:20px; background:#0056b3; color:white; border:none; border-radius:10px; font-size:20px;' onclick='act()'>ACEPTAR Y ENTRAR AL SISTEMA</button><script>function act(){ fetch('',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:crypto.randomUUID()})}).then(r=>r.json()).then(d=>window.location.href=d.map_url)}</script></body>")

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic = get_license_by_link(link_id)
    if not lic: return "DENEGADO", 403
    return render_template_string(VIEWER_HTML, expira=lic[1])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
