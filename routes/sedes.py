import logging
from typing import Any
from flask import Blueprint, render_template, jsonify

logger = logging.getLogger("siam.routes.sedes")
sedes_bp = Blueprint("sedes", __name__, url_prefix="/sedes")

# Static data for now (can be moved to DB later)
SEDES = [
    {
        "id": 1,
        "nombre": "Sede Principal Soacha",
        "direccion": "Cra. 7 # 15-42, Soacha, Cundinamarca",
        "telefono": "+57 300 123 4567",
        "horario": "Lun-Vie 7:00 AM - 6:00 PM, Sáb 8:00 AM - 1:00 PM",
        "latitud": 4.5773,
        "longitud": -74.2148,
        "servicios": ["Mantenimiento general", "Diagnóstico", "Frenos", "Suspensión", "Motor", "Transmisión"],
    }
]


@sedes_bp.route("/")
def index() -> Any:
    return render_template("sedes.html", sedes=SEDES)


@sedes_bp.route("/api")
def api() -> Any:
    return jsonify(SEDES)
