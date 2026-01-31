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
    <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css" />
    <style>
        body { margin:0; background:#000; font-family: 'Segoe UI', sans-serif; color:white; overflow:hidden; }
        #map { height: 60vh; width: 100%; border-bottom: 3px solid #0056b3; }
        .panel { height: 40vh; background:#111; padding:10px; display:flex; flex-direction:column; gap:4px; }
        .telemetria { display: flex; justify-content: space-around; background: #222; padding: 6px; border-radius: 8px; border: 1px solid #0af; color: #0af; font-family: monospace; }
        .search-box { display:flex; flex-direction:column; gap:4px; }
        input { padding:12px; border-radius:6px; border:1px solid #333; background:#222; color:white; font-size:14px; }
        .btn-group { display: flex; gap: 4px; }
        .btn-nav { flex: 2; background:#0056b3; color:white; border:none; padding:14px; border-radius:6px; font-weight:bold; cursor:pointer; }
        .btn-reset { flex: 1; background:#b30000; color:white; border:none; padding:14px; border-radius:6px; font-weight:bold; cursor:pointer; }
        #instrucciones { font-size:16px; color:#00ff00; font-weight:bold; text-align:center; min-height:1.2em; text-transform: uppercase; }
        .car-icon { filter: drop-shadow(0 0 10px #fff); z-index: 1000 !important; font-size: 45px; }
        .leaflet-routing-container { display: none; }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="panel">
        <div id="instrucciones">SISTEMA DE ASESORÍA LOGÍSTICA</div>
        <div class="telemetria">
            <div>VEL: <b id="vel">0</b> km/h</div>
            <div>DIST: <b id="dist">0.0</b> km</div>
            <div id="modo">ESPERA</div>
        </div>
        <div class="search-box">
            <input id="origen" placeholder="Punto de Origen">
            <input id="destino" placeholder="Destino Final">
        </div>
        <div class="btn-group">
            <button class="btn-nav" onclick="iniciarNavegacion()">INICIAR RUTA</button>
            <button class="btn-reset" onclick="reiniciarRuta()">NUEVA RUTA</button>
        </div>
        <div class="btn-group" style="margin-top:5px;">
            <button class="btn-reset" style="background:#444;" onclick="buscarCerca('fuel')">GASOLINERA</button>
            <button class="btn-reset" style="background:#444;" onclick="buscarCerca('restaurant')">COMIDA</button>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    <script>
        var map = L.map('map', { zoomControl: false }).setView([23.1136, -82.3666], 12);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

        var carMarker = L.marker([0,0], {
            icon: L.divIcon({html: '🚗', className: 'car-icon', iconSize: [50, 50]})
        }).addTo(map);

        var control = L.Routing.control({
            waypoints: [],
            router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1', profile: 'car' }),
            lineOptions: { styles: [{color: '#00ff00', opacity: 1, weight: 10}] },
            language: 'es',
            createMarker: function() { return null; }
        }).addTo(map);

        let ultimaVoz = "";

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
                hablar("Ruta calculada. Inicie el movimiento del vehículo.");
                activarMonitoreo();
            }
        }

        function activarMonitoreo() {
            navigator.geolocation.watchPosition(pos => {
                const latlng = L.latLng(pos.coords.latitude, pos.coords.longitude);
                const vel = pos.coords.speed ? Math.round(pos.coords.speed * 3.6) : 0;
                
                document.getElementById('vel').innerText = vel;
                carMarker.setLatLng(latlng);
                map.setView(latlng, 18);

                // Solo hablar si el carro se mueve (más de 5 km/h)
                if (vel > 5) {
                    procesarInstrucciones(latlng);
                    dibujarMurosRojos(latlng);
                }
            }, null, { enableHighAccuracy: true });
        }

        function dibujarMurosRojos(pos) {
            // Siluetas rojas (dos rayas) en las calles que no son el destino
            const angulo = 0.0004;
            const lineas = [
                [[pos.lat + angulo, pos.lng + angulo], [pos.lat + angulo + 0.0001, pos.lng + angulo + 0.0001]],
                [[pos.lat - angulo, pos.lng - angulo], [pos.lat - angulo - 0.0001, pos.lng - angulo - 0.0001]]
            ];
            lineas.forEach(l => {
                let pLine = L.polyline(l, {color: 'red', weight: 8, opacity: 0.8}).addTo(map);
                setTimeout(() => map.removeLayer(pLine), 3000);
            });
        }

        function procesarInstrucciones(pos) {
            // El sistema solo habla si hay una instrucción nueva del OSRM
            const activeRoute = control.getPlan().getWaypoints();
            if (activeRoute.length > 0) {
                // Aquí se activa la lógica de proximidad de Google Maps
            }
        }

        control.on('routesfound', function(e) {
            const instruccion = e.routes[0].instructions[0];
            if (instruccion && instruccion.text !== ultimaVoz) {
                document.getElementById('instrucciones').innerText = instruccion.text;
                hablar(instruccion.text);
                ultimaVoz = instruccion.text;
            }
        });

        function hablar(t) {
            window.speechSynthesis.cancel(); // Detiene cualquier voz anterior para que no se acumule
            const u = new SpeechSynthesisUtterance(t);
            u.lang = 'es-MX'; // Español latino/estándar
            u.rate = 1.0;
            window.speechSynthesis.speak(u);
        }

        function reiniciarRuta() {
            control.setWaypoints([]);
            document.getElementById('origen').value = "";
            document.getElementById('destino').value = "";
            document.getElementById('instrucciones').innerText = "ESPERANDO NUEVA RUTA";
            hablar("Sistema reiniciado.");
        }

        async function buscarCerca(tipo) {
            const pos = carMarker.getLatLng();
            const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${tipo}&lat=${pos.lat}&lon=${pos.lng}&zoom=15`);
            const d = await r.json();
            d.forEach(l => L.marker([l.lat, l.lon]).addTo(map).bindPopup(l.display_name).openPopup());
            hablar("Buscando " + tipo + " cerca de su posición.");
        }
    </script>
</body>
</html>
