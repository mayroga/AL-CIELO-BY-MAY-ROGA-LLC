import os, uuid, stripe, sqlite3
from flask import Flask, request, jsonify, redirect, render_template_string
from datetime import datetime, timedelta

app = Flask(__name__)

# --- CONFIGURACIÓN DE SEGURIDAD MAY ROGA LLC ---
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "sk_test_tu_llave")
stripe.api_key = STRIPE_SECRET_KEY
DB_PATH = "data.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS licencias 
            (link_id TEXT PRIMARY KEY, device_id TEXT, expira TEXT, activo INTEGER)""")
init_db()

# --- INTERFAZ DE NAVEGACIÓN "AL CIELO" ---
VIEWER_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <title>AL CIELO - Navegación Total Cuba</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css" />
    <style>
        body { margin:0; background:#000; font-family: sans-serif; color:white; overflow:hidden; }
        #map { height: 65vh; width: 100%; border-bottom: 2px solid #0059b3; }
        .ui { height: 35vh; background:#111; padding:15px; display:flex; flex-direction:column; gap:10px; }
        input { width: 92%; padding:12px; border-radius:8px; border:1px solid #333; background:#222; color:white; font-size:16px; }
        .btn-main { width: 100%; padding:15px; background:#0059b3; color:white; border:none; border-radius:8px; font-weight:bold; cursor:pointer; }
        .row { display:flex; gap:10px; }
        .btn-sec { flex:1; padding:10px; background:#333; color:white; border:none; border-radius:5px; font-size:12px; }
        @media print { .ui { display:none; } #map { height: 100vh; } }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="ui">
        <input id="start" placeholder="Inicio: Ej. Lawton, Habana">
        <input id="end" placeholder="Fin: Ej. Varadero o Maisí">
        <button class="btn-main" onclick="trazarRuta()">CALCULAR RUTA ASESORÍA</button>
        <div class="row">
            <button class="btn-sec" onclick="window.print()">REPORTE PDF</button>
            <button class="btn-sec" style="background:#b30000;" onclick="eliminarRastro()">BORRAR DATOS</button>
        </div>
        <div style="text-align:center; font-size:10px; color:#555;">
            AL CIELO by May Roga LLC | Jurisdicción USA | Expira: {{expira}}
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    <script>
        // SEGURIDAD: Auto-destrucción si expira
        const fechaExp = new Date("{{expira}}");
        if (new Date() > fechaExp) {
            alert("Licencia Expirada. Contacte a May Roga LLC.");
            localStorage.clear();
            window.location.href = "/";
        }

        // Mapa centrado en Cuba (Toda la isla)
        var map = L.map('map').setView([21.5218, -77.7812], 6);
        
        // Capas Híbridas (Protección Offline)
        L.tileLayer('/static/maps/cuba_tiles/{z}/{x}/{y}.png', { maxZoom: 18 }).addTo(map);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);

        var control = L.Routing.control({
            waypoints: [],
            router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1' }),
            lineOptions: { styles: [{color: '#00ff00', weight: 6}] },
            language: 'es'
        }).addTo(map);

        async function trazarRuta() {
            const s = document.getElementById('start').value;
            const e = document.getElementById('end').value;
            if(!s || !e) return;

            const res1 = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${s},Cuba`).then(r=>r.json());
            const res2 = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${e},Cuba`).then(r=>r.json());

            if(res1[0] && res2[0]) {
                const p1 = L.latLng(res1[0].lat, res1[0].lon);
                const p2 = L.latLng(res2[0].lat, res2[0].lon);
                control.setWaypoints([p1, p2]);
                map.fitBounds([p1, p2]);
                hablar("Ruta de asesoría calculada correctamente.");
            } else { alert("Ubicación no encontrada."); }
        }

        function hablar(t) {
            var m = new SpeechSynthesisUtterance(t);
            m.lang = 'es-US'; window.speechSynthesis.speak(m);
        }

        function eliminarRastro() {
            if(confirm("¿Borrar historial de May Roga LLC?")) {
                caches.delete('al-cielo-map-v1');
                localStorage.clear();
                window.location.href = "/";
            }
        }

        // Anticopia
        document.addEventListener('contextmenu', e => e.preventDefault());
    </script>
</body>
</html>
"""

# --- RUTAS DE LA APP ---

@app.route("/")
def index():
    return """
    <body style="text-align:center; font-family:sans-serif; padding-top:100px; background:#f4f4f4;">
        <h1 style="color:#0059b3;">AL CIELO</h1>
        <p>Asesoría Profesional de Navegación - May Roga LLC</p>
        <div style="margin:20px;"><a href="/pay/15" style="padding:15px 30px; background:blue; color:white; text-decoration:none; border-radius:5px;">10 DÍAS - $15.00</a></div>
        <div style="margin:20px;"><a href="/pay/25" style="padding:15px 30px; background:green; color:white; text-decoration:none; border-radius:5px;">28 DÍAS - $25.00</a></div>
    </body>
    """

@app.route("/pay/<int:price>")
def pay(price):
    link_id = str(uuid.uuid4())[:8]
    dias = 10 if price == 15 else 28
    expira = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO licencias VALUES (?, ?, ?, ?)", (link_id, None, expira, 1))
    return redirect(f"/activar/{link_id}")

@app.route("/activar/<link_id>")
def activar(link_id):
    return render_template_string("""
        <body style="text-align:center; padding:50px;">
            <h2>Activar Asesoría AL CIELO</h2>
            <p>Al presionar activar, este dispositivo quedará registrado.</p>
            <button onclick="act()" style="padding:20px; background:blue; color:white;">ACTIVAR AHORA</button>
            <script>
                function act(){
                    fetch('/registro/{{id}}', {method:'POST'})
                    .then(() => window.location.href='/viewer/{{id}}');
                }
            </script>
        </body>
    """, id=link_id)

@app.route("/registro/<link_id>", methods=["POST"])
def registro(link_id):
    # En producción usaríamos un ID real del dispositivo
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE licencias SET device_id='ACTIVO' WHERE link_id=?", (link_id,))
    return jsonify({"status": "ok"})

@app.route("/viewer/<link_id>")
def viewer(link_id):
    with sqlite3.connect(DB_PATH) as conn:
        lic = conn.execute("SELECT expira FROM licencias WHERE link_id=?", (link_id,)).fetchone()
    if lic:
        return render_template_string(VIEWER_HTML, expira=lic[0])
    return "Enlace Inválido", 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
