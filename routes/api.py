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
    descripcion = (data.get("descripcion") or "").strip()[:500]

    if latitud is None or longitud is None:
        return jsonify({"success": False, "error": "Latitud y longitud requeridas"}), 400

    try:
        asistencia = AsistenciaEmergencia(
            usuario_id=current_user.id,
            descripcion=descripcion or "Solicitud de asistencia por ubicación compartida",
            latitud=latitud,
            longitud=longitud,
            precision_metros=precision,
            estado="pendiente",
        )
        db.session.add(asistencia)
        safe_commit()
        logger.info("Asistencia creada desde ubicación: #%s (usuario %s)", asistencia.id, current_user.id)
        return json_success(
            {"id": asistencia.id, "estado": asistencia.estado},
            "Ubicación recibida. SIAM está buscando asistencia cercana.",
        )
    except Exception as e:
        db.session.rollback()
        logger.error("Error al guardar ubicación/asistencia", exc_info=True)
        return json_error("No se pudo guardar tu ubicación. Intenta nuevamente.")


@api_bp.route("/horas-disponibles")
@login_required
def horas_disponibles() -> Any:
    """Slots libres para una sede/fecha (staff y portal)."""
    from datetime import date as date_cls

    from services.sede_service import SedeService

    sede_id = request.args.get("sede_id", type=int)
    cita_id = request.args.get("cita_id", type=int)
    try:
        fecha = date_cls.fromisoformat(request.args.get("fecha", "") or "")
    except ValueError:
        return json_error("Fecha inválida.", status=400)

    try:
        horas = SedeService.horas_disponibles(sede_id or None, fecha, cita_id)
    except Exception:
        logger.error("Error consultando horas disponibles", exc_info=True)
        return json_error("No se pudieron consultar los horarios.", status=500)
    return jsonify({"fecha": fecha.isoformat(), "horas": horas})


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


@api_bp.route("/asistencia/<int:asistencia_id>/cancelar", methods=["POST"])
@login_required
def cancelar_asistencia(asistencia_id: int) -> Any:
    asistencia = AsistenciaEmergencia.query.filter_by(
        id=asistencia_id, usuario_id=current_user.id
    ).first()
    if not asistencia:
        return json_error("Solicitud de asistencia no encontrada.", status=404)
    if asistencia.estado in ("atendido", "cancelado"):
        return json_error("Esta solicitud ya no se puede cancelar.", status=400)
    asistencia.estado = "cancelado"
    try:
        safe_commit()
        logger.info("Asistencia #%s cancelada por usuario %s", asistencia.id, current_user.id)
        return json_success({"id": asistencia.id, "estado": asistencia.estado}, "Asistencia cancelada.")
    except Exception:
        db.session.rollback()
        return json_error("No se pudo cancelar la solicitud de asistencia.")
