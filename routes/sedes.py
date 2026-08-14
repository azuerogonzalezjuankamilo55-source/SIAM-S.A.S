import logging
from typing import Any
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required

from database.db import db
from database.commit import safe_commit, json_success, json_error
from decorators import staff_required
from models.asistencia import AsistenciaEmergencia

logger = logging.getLogger("siam.routes.sedes")
sedes_bp = Blueprint("sedes", __name__, url_prefix="/sedes")

# Datos estáticos de sedes (puede migrarse a DB más adelante)
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
    },
    {
        "id": 2,
        "nombre": "Sede Norte Bogotá",
        "direccion": "Av. Calle 80 # 92-40, Bogotá",
        "telefono": "+57 310 456 7890",
        "horario": "Lun-Vie 7:00 AM - 6:00 PM, Sáb 8:00 AM - 1:00 PM",
        "latitud": 4.7020,
        "longitud": -74.1038,
        "servicios": ["Diagnóstico", "Cambio de aceite", "Motos", "Frenos", "Alineación y balanceo"],
    },
    {
        "id": 3,
        "nombre": "Sede Sur Kennedy",
        "direccion": "Av. Boyacá # 39-10, Bogotá",
        "telefono": "+57 320 789 1234",
        "horario": "Lun-Sáb 7:30 AM - 6:00 PM",
        "latitud": 4.6266,
        "longitud": -74.1609,
        "servicios": ["Mantenimiento preventivo", "Repuestos", "Suspensión", "Electricidad automotriz"],
    },
    {
        "id": 4,
        "nombre": "Sede Occidente Fontibón",
        "direccion": "Cra. 100 # 17-35, Bogotá",
        "telefono": "+57 315 234 5678",
        "horario": "Lun-Vie 7:00 AM - 5:00 PM, Sáb 8:00 AM - 12:00 M",
        "latitud": 4.6683,
        "longitud": -74.1433,
        "servicios": ["Vehículos de carga", "Diagnóstico", "Frenos", "Aire acondicionado", "Asistencia"],
    },
]


@sedes_bp.route("/")
def index() -> Any:
    return render_template("sedes.html", sedes=SEDES)


@sedes_bp.route("/api")
def api() -> Any:
    return jsonify(SEDES)


@sedes_bp.route("/asistencias")
@login_required
@staff_required
def asistencias() -> Any:
    """Panel del personal: solicitudes de asistencia de emergencia."""
    estado = request.args.get("estado") or ""
    query = AsistenciaEmergencia.query
    if estado in ("pendiente", "en_camino", "atendido", "cancelado"):
        query = query.filter(AsistenciaEmergencia.estado == estado)
    asistencias = query.order_by(
        AsistenciaEmergencia.created_at.desc(), AsistenciaEmergencia.id.desc()
    ).all()
    return render_template(
        "sedes_asistencias.html", asistencias=asistencias, estado=estado, sedes=SEDES
    )


ESTADOS_ASISTENCIA = ("en_camino", "atendido", "cancelado")


@sedes_bp.route("/asistencias/<int:asistencia_id>/estado", methods=["POST"])
@login_required
@staff_required
def cambiar_estado(asistencia_id: int) -> Any:
    """Actualiza el estado de una solicitud (en_camino / atendido / cancelado)."""
    if request.is_json:
        nuevo_estado = (request.get_json(silent=True) or {}).get("estado", "")
    else:
        nuevo_estado = request.form.get("estado", "")
    if nuevo_estado not in ESTADOS_ASISTENCIA:
        return jsonify({"success": False, "error": "Estado no válido."}), 400

    asistencia = db.get_or_404(AsistenciaEmergencia, asistencia_id)
    if asistencia.estado in ("atendido", "cancelado"):
        return jsonify({"success": False, "error": "La solicitud ya está finalizada."}), 400

    asistencia.estado = nuevo_estado
    try:
        safe_commit()
    except Exception as e:
        db.session.rollback()
        return json_error(str(e), 500)
    logger.info("Asistencia %s marcada como %s", asistencia_id, nuevo_estado)
    return json_success({"estado": asistencia.estado}, "Estado actualizado.")
