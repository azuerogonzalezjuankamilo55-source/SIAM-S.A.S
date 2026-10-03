import logging
from typing import Any
from flask import Blueprint, flash, redirect, render_template, jsonify, request, url_for
from flask_login import login_required, current_user

from database.db import db
from database.commit import safe_commit, json_success, json_error
from decorators import roles_required, staff_required
from models.asistencia import AsistenciaEmergencia
from models.solicitud_asesor import SolicitudAsesor
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


# ---------------------------------------------------------------- asesorías

AVISOS_ASESOR = {
    "en_atencion": (
        "Solicitud en atención",
        "La administración ya está revisando tu solicitud de asesoría.",
    ),
    "atendida": (
        "Solicitud atendida",
        "Tu solicitud de asesoría fue atendida por la administración.",
    ),
    "cancelada": (
        "Solicitud cancelada",
        "La administración canceló tu solicitud de asesoría.",
    ),
}


@sedes_bp.route("/asesores")
@login_required
@roles_required("admin", "recepcion")
def asesores() -> Any:
    """Panel del personal: solicitudes de asesoría de los clientes."""
    estado = request.args.get("estado") or ""
    query = SolicitudAsesor.query
    if estado in SolicitudAsesor.ESTADOS:
        query = query.filter(SolicitudAsesor.estado == estado)
    solicitudes = query.order_by(
        SolicitudAsesor.created_at.desc(), SolicitudAsesor.id.desc()
    ).all()
    return render_template(
        "sedes_asesores.html",
        solicitudes=solicitudes,
        estado=estado,
    )


@sedes_bp.route("/asesores/<int:solicitud_id>/estado", methods=["POST"])
@login_required
@roles_required("admin", "recepcion")
def cambiar_estado_asesor(solicitud_id: int) -> Any:
    """El taller mueve la solicitud de asesoría y responde al cliente."""
    if request.is_json:
        nuevo_estado = (request.get_json(silent=True) or {}).get("estado", "")
        respuesta = (request.get_json(silent=True) or {}).get("respuesta", "")
    else:
        nuevo_estado = request.form.get("estado", "")
        respuesta = request.form.get("respuesta", "")

    # Filtro del panel que hizo el submit, para volver a la misma pestaña.
    estado_filtro = request.values.get("estado_filtro", "").strip()
    if estado_filtro not in SolicitudAsesor.ESTADOS:
        estado_filtro = ""

    if nuevo_estado not in SolicitudAsesor.ESTADOS:
        if request.is_json:
            return jsonify({"success": False, "error": "Estado no válido."}), 400
        flash("El estado indicado no es válido.", "danger")
        return redirect(url_for("sedes.asesores", estado=estado_filtro))

    solicitud = db.get_or_404(SolicitudAsesor, solicitud_id)
    if not solicitud.esta_abierta:
        if request.is_json:
            return jsonify({"success": False, "error": "La solicitud ya está finalizada."}), 400
        flash("Esa solicitud ya está finalizada.", "warning")
        return redirect(url_for("sedes.asesores", estado=estado_filtro))

    solicitud.estado = nuevo_estado
    respuesta = (respuesta or "").strip()[:2000]
    if respuesta:
        solicitud.respuesta = respuesta
    try:
        safe_commit()
    except Exception:
        db.session.rollback()
        logger.exception("No se pudo guardar el estado de la solicitud %s", solicitud_id)
        if not request.is_json:
            flash("No se pudo actualizar la solicitud.", "danger")
            return redirect(url_for("sedes.asesores", estado=estado_filtro))
        return json_error("No se pudo actualizar la solicitud.", status=500)

    # El estado ya quedo guardado: si el aviso al cliente falla, no se revierte.
    try:
        titulo, mensaje = AVISOS_ASESOR[nuevo_estado]
        if respuesta:
            mensaje = f"{mensaje} {respuesta}"
        if not NotificationService.notify_cliente(
            solicitud.cliente_id, "asesor", titulo, mensaje, url_for("portal.asesor")
        ):
            logger.warning(
                "Solicitud de asesoria %s sin cuenta de cliente para notificar", solicitud_id
            )
    except KeyError:
        # "pendiente" no es un cambio digno de aviso al cliente.
        pass
    except Exception:
        logger.exception(
            "Solicitud de asesoria %s actualizada a %s pero fallo la notificacion",
            solicitud_id,
            nuevo_estado,
        )

    logger.info(
        "Solicitud de asesoria %s marcada como %s por %s",
        solicitud_id,
        nuevo_estado,
        _actor(),
    )
    if not request.is_json:
        flash(f"Solicitud #{solicitud.id} actualizada a {solicitud.estado_label}.", "success")
        return redirect(url_for("sedes.asesores", estado=estado_filtro))
    return json_success(
        {"estado": solicitud.estado, "estado_label": solicitud.estado_label},
        "Solicitud actualizada.",
    )
