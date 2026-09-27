import logging
from typing import Any

from flask import Blueprint, request, jsonify, url_for
from flask_login import login_required, current_user

from database.db import db
from database.commit import safe_commit, json_success, json_error
from models.asistencia import AsistenciaEmergencia
from models.vehiculo import Vehiculo
from services.notification_service import NotificationService
from services.portal_service import PortalService
from services.vehiculo_service import VehiculoService

logger = logging.getLogger("siam.routes.api")
api_bp = Blueprint("api", __name__, url_prefix="/api")


class VehiculoNoPermitido(Exception):
    """El cliente intenta asociar un vehiculo que no le pertenece."""


def _vehiculo_del_cliente(vehiculo_id: Any, cliente) -> Vehiculo | None:
    """Resuelve un vehiculo SOLO si pertenece al cliente indicado.

    Un cliente no puede asociar a su solicitud el vehiculo de otro cliente
    cambiando el id en la peticion (fase 26.10). Omitir el vehiculo es valido
    (la solicitud se registra igual), pero referenciar uno ajeno es un
    intento de acceso a datos de terceros: se rechaza, no se ignora en
    silencio, porque ignorarlo ocultaria el fallo de seguridad al usuario.
    """
    if not vehiculo_id:
        return None
    if not cliente:
        raise VehiculoNoPermitido("El usuario no tiene un cliente asociado.")
    vehiculo = Vehiculo.query.filter_by(id=vehiculo_id, cliente_id=cliente.id).first()
    if not vehiculo:
        raise VehiculoNoPermitido("El vehiculo indicado no pertenece a tu cuenta.")
    return vehiculo


def _crear_solicitud_asistencia(
    *,
    descripcion: str,
    latitud: Any,
    longitud: Any,
    precision: Any,
    vehiculo_id: Any = None,
) -> AsistenciaEmergencia:
    """Guarda la solicitud de asistencia y notifica al personal del taller.

    Asocia la solicitud al cliente y (si se indico) a uno de sus vehiculos, de
    modo que el taller vea exactamente quien y que vehiculo la solicito.
    """
    cliente = PortalService.get_cliente_de_usuario(current_user)
    vehiculo = _vehiculo_del_cliente(vehiculo_id, cliente)

    solicitud = AsistenciaEmergencia(
        usuario_id=current_user.id,
        cliente_id=cliente.id if cliente else None,
        vehiculo_id=vehiculo.id if vehiculo else None,
        cliente_nombre=cliente.nombre if cliente else (current_user.nombre or None),
        telefono=(cliente.telefono if cliente else None) or None,
        descripcion=descripcion,
        latitud=latitud,
        longitud=longitud,
        precision_metros=precision,
        estado="pendiente",
    )
    db.session.add(solicitud)
    safe_commit()

    _notificar_asistencia_a_staff(solicitud, "nueva")
    return solicitud


def _notificar_asistencia_a_staff(
    solicitud: AsistenciaEmergencia, situacion: str = "nueva"
) -> None:
    """Notifica al personal el novedades de una solicitud de asistencia.

    `situacion`: "nueva" cuando el cliente la crea, "cancelada" cuando el
    mismo cliente la retira.
    """
    contexto = solicitud.vehiculo_label
    detalle = f" Vehículo: {contexto}." if contexto else ""
    if situacion == "cancelada":
        NotificationService.notify_staff(
            "asistencia",
            f"Solicitud de asistencia #{solicitud.id} cancelada",
            f"{solicitud.solicitante} canceló su solicitud de asistencia.{detalle}",
            url_for("sedes.asistencias"),
        )
        return
    NotificationService.notify_staff(
        "asistencia",
        f"Solicitud de asistencia #{solicitud.id}",
        f"{solicitud.solicitante} pidió asistencia en camino.{detalle}",
        url_for("sedes.asistencias"),
    )


def _detalle_solicitud(solicitud: AsistenciaEmergencia) -> dict:
    """Datos que el personal necesita para atender la solicitud."""
    return {
        "id": solicitud.id,
        "solicitante": solicitud.solicitante,
        "vehiculo": solicitud.vehiculo_label,
        "telefono": solicitud.telefono or "",
    }


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
    vehiculo_id = data.get("vehiculo_id")

    if latitud is None or longitud is None:
        return jsonify({"success": False, "error": "Latitud y longitud requeridas"}), 400

    try:
        solicitud = _crear_solicitud_asistencia(
            descripcion=descripcion or "Solicitud de asistencia por ubicación compartida",
            latitud=latitud,
            longitud=longitud,
            precision=precision,
            vehiculo_id=vehiculo_id,
        )
        logger.info(
            "Asistencia #%s creada desde ubicación (cliente %s)", solicitud.id, solicitud.cliente_id
        )
        return json_success(
            {"id": solicitud.id, "estado": solicitud.estado, **_detalle_solicitud(solicitud)},
            "Ubicación recibida. El taller ya fue notificado y busca asistencia cercana.",
        )
    except VehiculoNoPermitido as exc:
        return json_error(str(exc), status=403)
    except Exception:
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
        asistencias = (
            AsistenciaEmergencia.query.filter_by(usuario_id=current_user.id)
            .order_by(AsistenciaEmergencia.created_at.desc(), AsistenciaEmergencia.id.desc())
            .all()
        )
        return jsonify([a.to_dict() for a in asistencias])

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Datos inválidos"}), 400

    try:
        solicitud = _crear_solicitud_asistencia(
            descripcion=(data.get("descripcion") or "").strip()[:500],
            latitud=data.get("latitude"),
            longitud=data.get("longitude"),
            precision=data.get("accuracy"),
            vehiculo_id=data.get("vehiculo_id"),
        )
        logger.info(
            "Asistencia #%s creada (cliente %s, vehiculo %s)",
            solicitud.id,
            solicitud.cliente_id,
            solicitud.vehiculo_id,
        )
        return json_success(
            {"id": solicitud.id, **_detalle_solicitud(solicitud)},
            "Asistencia solicitada. El taller fue notificado.",
        )
    except VehiculoNoPermitido as exc:
        return json_error(str(exc), status=403)
    except Exception:
        db.session.rollback()
        logger.error("Error al crear asistencia", exc_info=True)
        return json_error("No se pudo crear la solicitud de asistencia.")


@api_bp.route("/vehiculos/mios")
@login_required
def vehiculos_mios() -> Any:
    """Vehiculos del cliente autenticado, listos para el selector de asistencia."""
    cliente = PortalService.get_cliente_de_usuario(current_user)
    if not cliente:
        return jsonify([])
    return jsonify(VehiculoService.listar_para_select(cliente.id))


@api_bp.route("/asistencia/<int:asistencia_id>/cancelar", methods=["POST"])
@login_required
def cancelar_asistencia(asistencia_id: int) -> Any:
    solicitud = AsistenciaEmergencia.query.filter_by(
        id=asistencia_id, usuario_id=current_user.id
    ).first()
    if not solicitud:
        return json_error("Solicitud de asistencia no encontrada.", status=404)
    if solicitud.estado in ("atendido", "cancelado"):
        return json_error("Esta solicitud ya no se puede cancelar.", status=400)
    solicitud.estado = "cancelado"
    try:
        safe_commit()
        _notificar_asistencia_a_staff(solicitud, "cancelada")
        logger.info("Asistencia #%s cancelada por usuario %s", solicitud.id, current_user.id)
        return json_success(
            {"id": solicitud.id, "estado": solicitud.estado},
            "Asistencia cancelada. El taller fue notificado.",
        )
    except Exception:
        db.session.rollback()
        return json_error("No se pudo cancelar la solicitud de asistencia.")
