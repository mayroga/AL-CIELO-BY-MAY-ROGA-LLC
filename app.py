import os
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)

# Base de datos (Simulada para el ejemplo, usar PostgreSQL en producción)
db_licencias = {}

@app.route('/comprar', methods=['POST'])
def comprar():
    plan = request.json.get('plan') # '10dias' o '28dias'
    dias = 10 if plan == '10dias' else 28
    link_id = str(uuid.uuid4())[:8]
    
    # EL TIEMPO CORRE DESDE EL MOMENTO DE LA COMPRA
    fecha_compra = datetime.now()
    fecha_expira = fecha_compra + timedelta(days=dias)
    
    db_licencias[link_id] = {
        "dispositivos": [],
        "expira": fecha_expira.isoformat(),
        "status": "ACTIVE",
        "legal_firmado": False
    }
    return jsonify({"link": f"https://al-cielo.render.com/activar/{link_id}"})

@app.route('/validar_activacion/<link_id>', methods=['POST'])
def validar(link_id):
    data = request.json
    device_id = data.get('device_id')
    acepta_terminos = data.get('acepta_terminos')

    if link_id not in db_licencias:
        return jsonify({"status": "RED", "msg": "Link Inválido"}), 404
    
    lic = db_licencias[link_id]
    
    if not acepta_terminos:
        return jsonify({"status": "RED", "msg": "Debe aceptar el deslinde legal"}), 403

    # Control de 2 dispositivos: El segundo desactiva al primero
    if device_id not in lic['dispositivos']:
        if len(lic['dispositivos']) >= 2:
             return jsonify({"status": "RED", "msg": "Límite excedido. Servicio revocado."}), 403
        lic['dispositivos'].append(device_id)
        lic['active_now'] = device_id # Solo el último es el activo

    return jsonify({
        "status": "GREEN",
        "expires": lic['expira'],
        "map_url": "https://al-cielo.render.com/download/cuba_full.mbtiles",
        "msg": "AL CIELO Activado. Navegación Offline Habilitada."
    })
