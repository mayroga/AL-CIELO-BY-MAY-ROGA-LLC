import os
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)

# CONFIGURACIÓN DESDE EL PANEL DE RENDER (ENVIRONMENT VARIABLES)
ADMIN_USER = os.getenv('ADMIN_USERNAME')
ADMIN_PASS = os.getenv('ADMIN_PASSWORD')
BASE_URL = "https://al-cielo-by-may-roga-llc.onrender.com"

# BASE DE DATOS EN MEMORIA (Licencias y dispositivos)
db_licencias = {}

# --- PANEL DE ADMINISTRACIÓN SEGURO ---
@app.route('/admin/generar', methods=['GET', 'POST'])
def admin_panel():
    if request.method == 'POST':
        user = request.form.get('username')
        password = request.form.get('password')
        plan = request.form.get('plan')

        if user != ADMIN_USER or password != ADMIN_PASS:
            return "Acceso Denegado: Credenciales Incorrectas", 403

        link_id = str(uuid.uuid4())[:8]
        dias = int(plan)
        expiracion = datetime.now() + timedelta(days=dias)

        db_licencias[link_id] = {
            "devices": [],      # Lista de device_id autorizados
            "active_device": None,  # Device activo actualmente
            "expira": expiracion.strftime("%Y-%m-%d %H:%M:%S")
        }

        return f"""
            <div style="font-family:sans-serif; text-align:center; padding:20px;">
                <h2 style="color:green;">Link Generado con Éxito</h2>
                <p>Copia y envía este link al residente en USA:</p>
                <div style="background:#eee; padding:10px; border-radius:5px; font-weight:bold;">
                    {BASE_URL}/activar/{link_id}
                </div>
                <br><a href='/admin/generar'>Crear otro link</a>
            </div>
        """

    return f"""
        <div style="font-family:sans-serif; text-align:center; padding-top:50px;">
            <img src="https://al-cielo-by-may-roga-llc.onrender.com/static/logo.png" width="100">
            <h2>AL CIELO - Panel de Control</h2>
            <form method="post" style="display:inline-block; text-align:left; border:1px solid #ccc; padding:20px; border-radius:10px;">
                <label>Usuario:</label><br>
                <input type="text" name="username" required><br><br>
                <label>Contraseña:</label><br>
                <input type="password" name="password" required><br><br>
                <label>Plan de Servicio:</label><br>
                <select name="plan">
    <option value="30">TEST INTERNO – 30 DÍAS (SOLO ADMIN)</option>
    <option value="1">TEST – 24h (GRATIS)</option>
    <option value="10">10 Días ($15)</option>
    <option value="28">28 Días ($25)</option>
</select><br><br>
                <button type="submit" style="width:100%; padding:10px; background:black; color:white; border:none; border-radius:5px;">GENERAR ACCESO</button>
            </form>
        </div>
    """

# --- ACTIVACIÓN DE LICENCIA Y DEVICE ---
@app.route('/activar/<link_id>', methods=['GET', 'POST'])
def activar(link_id):
    if link_id not in db_licencias:
        return "Link no válido o vencido. Contacte a May Roga LLC.", 404

    licencia = db_licencias[link_id]

    if request.method == 'POST':
        data = request.json
        device_id = data.get("device_id")
        legal_ok = data.get("legal_ok")

        if not legal_ok:
            return jsonify({"error": "Debe aceptar los términos legales"}), 403

        # Si el dispositivo no está registrado y hay espacio
        if device_id not in licencia["devices"]:
            if len(licencia["devices"]) < 2:
                licencia["devices"].append(device_id)
            else:
                return jsonify({"error": "Licencia activada en 2 dispositivos. Compre otra licencia."}), 403

        # Solo un device puede estar activo a la vez
        licencia["active_device"] = device_id

        return jsonify({
            "status": "OK",
            "message": "Licencia activada correctamente",
            "expira": licencia["expira"],
            "map_url": f"{BASE_URL}/static/maps/cuba_full.mbtiles"
        })

    # GET muestra la info básica con aviso legal
    return render_template_string("""
        <h1>Bienvenido a AL CIELO</h1>
        <p>Licencia válida hasta: {{expira}}</p>
        <p>Esta licencia se puede activar en máximo 2 dispositivos, pero solo uno funcionará a la vez.</p>
    """, expira=licencia["expira"])


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
