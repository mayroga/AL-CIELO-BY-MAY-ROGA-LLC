import os
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timedelta
import stripe
import uuid

app = Flask(__name__)

# CONFIGURACIÓN DE VARIABLES DE ENTORNO (YA EN RENDER)
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"

# BASE DE DATOS (Simulada - Se recomienda PostgreSQL para persistencia total)
db_licencias = {}

# --- INTERFAZ DE ACTIVACIÓN CON BLINDAJE LEGAL ---
HTML_ACTIVACION = """
<!DOCTYPE html>
<html>
<head>
    <title>AL CIELO - Activación</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; padding: 20px; text-align: center; background: #f4f4f4; }
        .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 400px; margin: auto; }
        .legal { font-size: 12px; text-align: justify; border: 1px solid #ccc; padding: 10px; height: 100px; overflow-y: scroll; margin-bottom: 20px; }
        button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; width: 100%; }
        button:disabled { background: #ccc; }
    </style>
</head>
<body>
    <div class="card">
        <h1>AL CIELO</h1>
        <p>Servicio de May Roga LLC</p>
        <div class="legal">
            DERECHOS Y RESPONSABILIDADES: Al activar este servicio, yo, como residente o ciudadano americano, declaro que soy el único responsable del uso de esta herramienta. AL CIELO es un software de consulta de datos para uso personal. May Roga LLC no se responsabiliza por el uso del mismo fuera de los Estados Unidos o por terceros. El servicio es intransferible y el mal uso anula la licencia sin derecho a reclamación.
        </div>
        <label><input type="checkbox" id="acepto"> He leído y acepto la responsabilidad total.</label><br><br>
        <button id="btn" onclick="procesar()" disabled>ACTIVAR MAPA OFFLINE</button>
    </div>
    <script>
        const cb = document.getElementById('acepto');
        const btn = document.getElementById('btn');
        cb.onchange = () => { btn.disabled = !cb.checked; };

        async function procesar() {
            const devId = navigator.userAgent + Math.random(); // ID temporal del dispositivo
            const res = await fetch(window.location.href, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ device_id: devId, acepta: true })
            });
            const data = await res.json();
            if(data.status === "GREEN") {
                alert("ACTIVADO. Vence: " + data.expira + ". Ya puede usar el mapa offline.");
                // Aquí la app descarga el mapa automáticamente
            } else { alert("Error: " + data.msg); }
        }
    </script>
</body>
</html>
"""

# --- RUTAS DEL SISTEMA ---

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            # Definir plan por monto ($15 o $25)
            dias = 10 if session['amount_total'] <= 1500 else 28
            link_id = str(uuid.uuid4())[:8]
            
            # EL TIEMPO CORRE DESDE LA COMPRA
            expiracion = datetime.now() + timedelta(days=dias)
            
            db_licencias[link_id] = {
                "devices": [],
                "expira": expiracion.strftime("%Y-%m-%d %H:%M:%S"),
                "dias": dias
            }
            print(f"LINK GENERADO: {BASE_URL}/activar/{link_id}")
        return jsonify(success=True)
    except Exception as e:
        return str(e), 400

@app.route('/activar/<link_id>', methods=['GET', 'POST'])
def activar(link_id):
    if link_id not in db_licencias:
        return "Link no válido o expirado", 404
    
    lic = db_licencias[link_id]

    if request.method == 'POST':
        data = request.json
        dev_id = data.get('device_id')
        
        # CONTROL DE DISPOSITIVOS (MÁXIMO 2, EL 2DO MATA AL 1RO)
        if dev_id not in lic['devices']:
            if len(lic['devices']) >= 2:
                return jsonify({"status": "RED", "msg": "Límite de dispositivos alcanzado. Servicio revocado."}), 403
            lic['devices'].append(dev_id)
            lic['activo_actual'] = dev_id # El último que entra es el dueño

        return jsonify({
            "status": "GREEN",
            "expira": lic['expira'],
            "msg": "Licencia validada correctamente."
        })

    return render_template_string(HTML_ACTIVACION)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
