import os, uuid, time, stripe, math
from flask import Flask, request, jsonify, redirect, render_template_string
from datetime import datetime, timedelta
from database import init_db, create_license, get_license_by_link, get_license_by_session, set_active_device

# =========================
# CONFIGURACIÓN BASE
# =========================
app = Flask(__name__, static_url_path='/static', static_folder='static')
init_db()

BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
stripe.api_key = STRIPE_SECRET_KEY

# =========================
# PLANES (NO TOCAR)
# =========================
PLANES = {
    "price_1Sv5uXBOA5mT4t0PtV7RaYCa": [15.00, 10, "Plan 10 Días"],
    "price_1Sv69jBOA5mT4t0PUA7yiisS": [25.00, 28, "Plan 28 Días"],
    "price_1Sv6H2BOA5mT4t0PppizlRAK": [0.00, 20, "Prueba Admin ($0.00)"]
}

# =========================
# HTML VISOR OFFLINE PRO
# =========================
VIEWER_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>AL CIELO – Navegación Offline Cuba</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>

<style>
body{margin:0;background:#000;color:#0ff;font-family:Segoe UI}
#map{height:65vh}
.panel{height:35vh;background:#060606;padding:10px}
.tele{display:flex;justify-content:space-around;font-family:monospace}
input,button{width:100%;padding:12px;margin-top:4px;border-radius:6px;border:none}
button{background:#0056b3;color:#fff;font-weight:bold}
#msg{color:#0f0;font-weight:bold;text-align:center}
.car{font-size:42px;filter:drop-shadow(0 0 6px #fff)}
</style>
</head>

<body>
<div id="map"></div>
<div class="panel">
  <div id="msg">SISTEMA AL CIELO ACTIVO</div>
  <div class="tele">
    <div>VEL <span id="vel">0</span> km/h</div>
    <div>DIST <span id="dist">0</span> km</div>
    <div id="modo">OFFLINE</div>
  </div>
  <input id="o" placeholder="Origen">
  <input id="d" placeholder="Destino">
  <button onclick="go()">INICIAR RUTA</button>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<script>
/* =========================
   MAPA OFFLINE
========================= */
const map = L.map('map',{zoomControl:false}).setView([23.11,-82.36],13);
L.tileLayer('/static/maps/cuba_tiles/{z}/{x}/{y}.png',{
  maxZoom:18,minZoom:6
}).addTo(map);

const car = L.marker([0,0],{
  icon:L.divIcon({html:"🚗",className:"car"})
}).addTo(map);

/* =========================
   VARIABLES
========================= */
let ruta=[], indice=0, distancia=0;
let ultimaOrden="";
let corredores=[];

/* =========================
   VOZ
========================= */
function hablar(t){
  if(t===ultimaOrden) return;
  ultimaOrden=t;
  speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(t);
  u.lang="es-ES";
  speechSynthesis.speak(u);
  document.getElementById("msg").innerText=t;
}

/* =========================
   BUSQUEDA ONLINE SOLO 20s
========================= */
async function buscar(q){
  const r=await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${q},Cuba&limit=1`);
  const d=await r.json();
  return d.length? [parseFloat(d[0].lat),parseFloat(d[0].lon)] : null;
}

/* =========================
   CREAR RUTA SIMPLIFICADA
========================= */
function crearRuta(a,b){
  ruta=[];
  for(let i=0;i<=30;i++){
    ruta.push([
      a[0]+(b[0]-a[0])*i/30,
      a[1]+(b[1]-a[1])*i/30
    ]);
  }
  L.polyline(ruta,{color:"#00ff00",weight:10}).addTo(map);
  crearCorredores();
}

/* =========================
   CORREDORES (NO DESVÍO)
========================= */
function crearCorredores(){
  corredores.forEach(c=>map.removeLayer(c));
  corredores=[];
  for(let i=0;i<ruta.length-1;i++){
    const p=ruta[i];
    const d=0.00025;
    const poly=L.polygon([
      [p[0]+d,p[1]+d],
      [p[0]+d,p[1]-d],
      [p[0]-d,p[1]-d],
      [p[0]-d,p[1]+d]
    ],{color:"#ff0000",fillOpacity:0.15});
    poly.addTo(map);
    corredores.push(poly);
  }
}

/* =========================
   MONITOREO GPS
========================= */
navigator.geolocation.watchPosition(pos=>{
  const lat=pos.coords.latitude;
  const lon=pos.coords.longitude;
  car.setLatLng([lat,lon]);
  map.setView([lat,lon],17);

  const vel=Math.round((pos.coords.speed||0)*3.6);
  document.getElementById("vel").innerText=vel;

  if(ruta.length){
    const t=ruta[indice];
    const d=Math.hypot(lat-t[0],lon-t[1]);
    if(d<0.0003 && indice<ruta.length-1){
      indice++;
      hablar("Continúe");
    }
    if(d>0.001){
      hablar("Fuera de ruta, corrigiendo");
      indice=0;
    }
  }
},{enableHighAccuracy:true});

/* =========================
   INICIAR
========================= */
async function go(){
  const a=await buscar(o.value);
  const b=await buscar(d.value);
  if(!a||!b){hablar("Destino no encontrado");return;}
  crearRuta(a,b);
  hablar("Ruta creada, inicie marcha");
}
</script>
</body>
</html>
"""

# =========================
# RUTAS FLASK (SIN CAMBIOS)
# =========================
@app.route("/")
def home():
    html = "<div style='background:black;color:white;text-align:center;padding:40px'>"
    html += "<h1>AL CIELO</h1><p>MAY ROGA LLC</p><hr>"
    for pid,(p,d,n) in PLANES.items():
        html += f"<a href='/checkout/{pid}' style='display:block;background:#0056b3;color:white;padding:18px;margin:10px'>{n} ${p}</a>"
    html += "</div>"
    return html

@app.route("/checkout/<pid>")
def checkout(pid):
    if PLANES[pid][0]==0:
        lid=str(uuid.uuid4())[:8]
        create_license(lid,f"ADMIN_{lid}",
        (datetime.utcnow()+timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"))
        return redirect(f"/activar/{lid}")

    session=stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[{"price":pid,"quantity":1}],
        success_url=f"{BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=BASE_URL
    )
    return redirect(session.url)

@app.route("/success")
def success():
    time.sleep(5)
    return redirect(f"/link/{request.args.get('session_id')}")

@app.route("/link/<session_id>")
def link(session_id):
    lid=get_license_by_session(session_id)
    return redirect(f"/activar/{lid}")

@app.route("/activar/<lid>",methods=["GET","POST"])
def activar(lid):
    if request.method=="POST":
        set_active_device(lid,request.json["device_id"])
        return jsonify({"map_url":f"/viewer/{lid}"})
    return "<button onclick='fetch(\"\",{method:\"POST\",headers:{\"Content-Type\":\"application/json\"},body:JSON.stringify({device_id:crypto.randomUUID()})}).then(r=>r.json()).then(d=>location=d.map_url)'>ACTIVAR</button>"

@app.route("/viewer/<lid>")
def viewer(lid):
    if not get_license_by_link(lid): return "DENEGADO",403
    return render_template_string(VIEWER_HTML)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)
