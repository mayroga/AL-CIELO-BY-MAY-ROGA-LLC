import os, uuid, time
from flask import Flask, request, jsonify, redirect, render_template_string
from datetime import datetime, timedelta
from database import init_db, create_license, get_license_by_link, get_license_by_session, set_active_device

app = Flask(__name__, static_url_path='/static', static_folder='static')
init_db()

BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"

PLANES = {
    "price_1Sv5uXBOA5mT4t0PtV7RaYCa": [15.00, 10, "Plan 10 Días"],
    "price_1Sv69jBOA5mT4t0PUA7yiisS": [25.00, 28, "Plan 28 Días"],
    "price_1Sv6H2BOA5mT4t0PppizlRAK": [0.00, 20, "Prueba Admin ($0.00)"]
}

VIEWER_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>AL CIELO - Navegación Cuba</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css"/>
    <style>
        body {margin:0;background:#000;color:white;font-family:sans-serif;overflow:hidden;}
        #map {height:60vh;width:100%;border-bottom:3px solid #0056b3;}
        .panel {height:40vh;background:#111;padding:10px;display:flex;flex-direction:column;gap:5px;}
        .telemetria {display:flex;justify-content:space-around;background:#222;padding:6px;border-radius:8px;border:1px solid #0af;color:#0af;font-family:monospace;}
        input {padding:12px;border-radius:6px;border:1px solid #333;background:#222;color:white;font-size:14px;}
        .btn-group {display:flex;gap:4px;}
        .btn-nav {flex:2;background:#0056b3;color:white;border:none;padding:14px;border-radius:6px;font-weight:bold;cursor:pointer;}
        .btn-reset {flex:1;background:#b30000;color:white;border:none;padding:14px;border-radius:6px;font-weight:bold;cursor:pointer;}
        #instrucciones {font-size:16px;color:#00ff00;font-weight:bold;text-align:center;min-height:1.2em;text-transform:uppercase;}
        .car-icon {filter: drop-shadow(0 0 10px #fff);z-index:1000 !important;font-size:45px;}
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
        <div>
            <input id="origen" placeholder="Punto de Origen en Cuba">
            <input id="destino" placeholder="Destino Final en Cuba">
        </div>
        <div class="btn-group">
            <button class="btn-nav" onclick="iniciarNavegacion()">INICIAR RUTA</button>
            <button class="btn-reset" onclick="reiniciarRuta()">NUEVA RUTA</button>
        </div>
    </div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
<script>
var map = L.map('map', {zoomControl:true}).setView([21.5218, -77.7812], 6); // Centro Cuba
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: 'Map data © <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors'
}).addTo(map);

var carMarker = L.marker([21.5218, -77.7812], {
    icon: L.divIcon({html:'🚗', className:'car-icon', iconSize:[50,50]})
}).addTo(map);

var control = L.Routing.control({
    waypoints: [],
    router: L.Routing.osrmv1({serviceUrl:'https://router.project-osrm.org/route/v1', profile:'car'}),
    lineOptions: {styles:[{color:'#00ff00',opacity:1,weight:8}]},
    createMarker: function() { return null; },
    routeWhileDragging: false
}).addTo(map);

let ultimaVoz="";

async function buscarLugar(q){
    if(!q) return null;
    const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${q},Cuba&limit=1`);
    const d = await r.json();
    return d.length > 0 ? L.latLng(d[0].lat, d[0].lon) : null;
}

async function iniciarNavegacion(){
    const p1 = await buscarLugar(document.getElementById('origen').value);
    const p2 = await buscarLugar(document.getElementById('destino').value);
    if(!p1 || !p2){ alert("No se encontraron ambos puntos en Cuba."); return; }
    control.setWaypoints([p1,p2]);
    hablar("Ruta calculada. Inicie el movimiento del vehículo.");
    activarMonitoreo();
}

function activarMonitoreo(){
    navigator.geolocation.watchPosition(pos=>{
        const latlng=L.latLng(pos.coords.latitude,pos.coords.longitude);
        const vel=pos.coords.speed?Math.round(pos.coords.speed*3.6):0;
        document.getElementById('vel').innerText=vel;
        carMarker.setLatLng(latlng);
        map.setView(latlng,16);
    }, null, {enableHighAccuracy:true});
}

control.on('routesfound',function(e){
    const route=e.routes[0];
    if(route.legs && route.legs[0].steps.length>0){
        const instruccion=route.legs[0].steps[0].maneuver.instruction;
        if(instruccion && instruccion!==ultimaVoz){
            document.getElementById('instrucciones').innerText=instruccion;
            hablar(instruccion);
            ultimaVoz=instruccion;
        }
    }
});

function hablar(texto){
    window.speechSynthesis.cancel();
    const u=new SpeechSynthesisUtterance(texto);
    u.lang='es-MX';
    u.rate=1.0;
    window.speechSynthesis.speak(u);
}

function reiniciarRuta(){
    control.setWaypoints([]);
    document.getElementById('origen').value="";
    document.getElementById('destino').value="";
    document.getElementById('instrucciones').innerText="ESPERANDO NUEVA RUTA";
    hablar("Sistema reiniciado.");
}
</script>
</body>
</html>
"""

@app.route("/")
def home():
    html = '<div style="max-width:400px;margin:auto;text-align:center;font-family:sans-serif;background:#000;color:white;padding:40px;border-radius:20px;border:2px solid #0056b3;">'
    html += '<h1>AL CIELO</h1><p>MAY ROGA LLC</p><hr>'
    for pid,(p,d,n) in PLANES.items():
        html += f'<a href="/checkout/{pid}" style="display:block;background:#0056b3;color:white;padding:18px;margin:15px 0;text-decoration:none;border-radius:12px;font-weight:bold;">{n} - ${p}</a>'
    html += '</div>'
    return html

@app.route("/checkout/<pid>")
def checkout(pid):
    if pid == "price_1Sv6H2BOA5mT4t0PppizlRAK":
        lid=str(uuid.uuid4())[:8]
        create_license(lid,f"ADMIN_{lid}",(datetime.utcnow()+timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"))
        return redirect(f"/activar/{lid}")
    return "Pago vía Stripe no implementado en esta versión demo."

@app.route("/activar/<link_id>",methods=["GET","POST"])
def activar(link_id):
    if request.method=="POST":
        if not request.json.get("legal_ok"):
            return jsonify({"error":"Consentimiento legal requerido"}),403
        set_active_device(link_id, request.json.get("device_id"))
        return jsonify({"status":"OK","map_url":f"/viewer/{link_id}"})
    return render_template_string("""
<body style='background:#000;color:white;text-align:center;padding-top:100px;'>
<h2>AL CIELO BY MAY ROGA LLC</h2>
<label><input type="checkbox" id="check-legal"> Acepto todas las condiciones legales y atribución OSM</label><br><br>
<button style='padding:20px;background:#0056b3;color:white;border:none;border-radius:10px;font-size:20px;' onclick='act()'>ACEPTAR Y ENTRAR AL SISTEMA</button>
<script>
function act(){
  if(!document.getElementById("check-legal").checked){alert("Debe aceptar el consentimiento legal");return;}
  fetch("",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({device_id:crypto.randomUUID(),legal_ok:true})})
  .then(r=>r.json()).then(d=>window.location.href=d.map_url);
}
</script></body>
""")

@app.route("/viewer/<link_id>")
def viewer(link_id):
    lic=get_license_by_link(link_id)
    if not lic: return "DENEGADO",403
    return render_template_string(VIEWER_HTML, expira=lic[1])

if __name__=="__main__":
    app.run(host="0.0.0.0", port=10000)
