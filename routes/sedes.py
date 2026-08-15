import logging
from typing import Any
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required

from database.db import db
from database.commit import safe_commit, json_success, json_error
from decorators import staff_required
from models.asistencia import AsistenciaEmergencia
from services.sede_service import SedeService

logger = logging.getLogger("siam.routes.sedes")
sedes_bp = Blueprint("sedes", __name__, url_prefix="/sedes")


@sedes_bp.route("/")
def index() -> Any:
    return render_template("sedes.html", sedes=SedeService.listar())


@sedes_bp.route("/api")
def api() -> Any:
    return jsonify(SedeService.listar())


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
        "sedes_asistencias.html", asistencias=asistencias, estado=estado, sedes=SedeService.listar()
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
