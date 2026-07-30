import logging
from typing import Any
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from database.db import db
from database.commit import safe_commit, json_success, json_error
from models.asistencia import AsistenciaEmergencia

logger = logging.getLogger("siam.routes.api")
api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/ubicacion", methods=["POST"])
@login_required
def recibir_ubicacion() -> Any:
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Datos inválidos"}), 400

    latitud = data.get("latitude")
    longitud = data.get("longitude")
    precision = data.get("accuracy")

    if latitud is None or longitud is None:
        return jsonify({"success": False, "error": "Latitud y longitud requeridas"}), 400

    logger.info("Ubicación recibida de usuario %s: lat=%s, lng=%s", current_user.id, latitud, longitud)
    return jsonify({"success": True, "message": "Ubicación recibida correctamente."})


@api_bp.route("/asistencia", methods=["GET", "POST"])
@login_required
def asistencia() -> Any:
    if request.method == "GET":
        asistencias = AsistenciaEmergencia.query.filter_by(usuario_id=current_user.id).order_by(
            AsistenciaEmergencia.created_at.desc()
        ).all()
        return jsonify([
            {
                "id": a.id,
                "descripcion": a.descripcion,
                "estado": a.estado,
                "fecha": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "",
            }
            for a in asistencias
        ])

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Datos inválidos"}), 400

    try:
        asistencia = AsistenciaEmergencia(
            usuario_id=current_user.id if current_user.is_authenticated else None,
            descripcion=data.get("descripcion", ""),
            latitud=data.get("latitude"),
            longitud=data.get("longitude"),
            precision_metros=data.get("accuracy"),
            estado="pendiente",
        )
        db.session.add(asistencia)
        safe_commit()
        logger.info("Asistencia creada: #%s", asistencia.id)
        return json_success({"id": asistencia.id}, "Asistencia solicitada correctamente.")
    except Exception as e:
        db.session.rollback()
        logger.error("Error al crear asistencia", exc_info=True)
        return json_error("No se pudo crear la solicitud de asistencia.")
