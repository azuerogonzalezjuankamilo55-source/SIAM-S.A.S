import logging
from typing import Any
from flask import Blueprint, render_template, jsonify, request, url_for
from flask_login import login_required, current_user

from database.db import db
from database.commit import safe_commit, json_success, json_error
from decorators import staff_required
from models.asistencia import AsistenciaEmergencia
from services.notification_service import NotificationService
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

#: Mensaje que recibe el cliente segun el estado que fija el taller.
AVISOS_ASISTENCIA = {
    "en_camino": (
        "Asistencia en camino",
        "El taller ya envió el equipo de asistencia. Puedes seguir el seguimiento desde Sedes y Asistencia.",
    ),
    "atendido": (
        "Asistencia atendida",
        "Tu solicitud de asistencia fue atendida por el taller.",
    ),
    "cancelado": (
        "Asistencia cancelada por el taller",
        "El taller canceló tu solicitud de asistencia. Contacta al taller si necesitas ayuda.",
    ),
}


def _actor() -> str:
    return getattr(current_user, "nombre", "personal")


def _notificar_cliente_asistencia(
    asistencia: AsistenciaEmergencia, estado_anterior: str, estado_nuevo: str
) -> None:
    """Avisa al cliente que el taller movió su solicitud (fase 26.7).

    La notificación es real: se persiste en la tabla `notificaciones` del
    usuario del cliente y aparece en su campana y en /notificaciones.
    """
    titulo, mensaje = AVISOS_ASISTENCIA[estado_nuevo]
    vehiculo = asistencia.vehiculo_label
    if vehiculo:
        mensaje = f"{mensaje} Vehículo: {vehiculo}."

    if not NotificationService.notify_cliente(
        asistencia.cliente_id,
        "asistencia",
        titulo,
        mensaje,
        url_for("sedes.index"),
    ):
        # Sin usuario vinculado no hay a quién avisar: se deja traza para que el
        # taller lo sepa en vez de creer que el cliente fue notificado.
        logger.warning(
            "Asistencia #%s cambió de %s a %s pero el cliente %s no tiene cuenta para notificar",
            asistencia.id,
            estado_anterior,
            estado_nuevo,
            asistencia.cliente_id,
        )


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

    estado_anterior = asistencia.estado
    asistencia.estado = nuevo_estado
    try:
        safe_commit()
    except Exception:
        db.session.rollback()
        logger.exception("No se pudo guardar el estado de la asistencia %s", asistencia_id)
        return json_error("No se pudo actualizar el estado de la solicitud.", status=500)

    # La solicitud ya quedo guardada: si el aviso al cliente falla, el estado no
    # se revierte (el commit ya ocurrio) y no se le reporta un error al taller
    # que haria pensar que la operacion fallo.
    try:
        _notificar_cliente_asistencia(asistencia, estado_anterior, nuevo_estado)
    except Exception:
        logger.exception(
            "Asistencia %s actualizada a %s pero fallo la notificacion al cliente",
            asistencia_id,
            nuevo_estado,
        )

    logger.info(
        "Asistencia %s marcada como %s por %s", asistencia_id, nuevo_estado, _actor()
    )
    return json_success({"estado": asistencia.estado}, "Estado actualizado.")
