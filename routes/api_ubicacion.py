import logging
from typing import Any

from flask import Blueprint, request
from flask_login import login_required, current_user

from database.db import db
from database.commit import safe_commit, json_success, json_error
from decorators import staff_required
from services.portal_service import PortalService
from services.ubicacion_service import UbicacionService, UbicacionError

logger = logging.getLogger("siam.routes.api_ubicacion")
api_ubicacion_bp = Blueprint("api_ubicacion", __name__, url_prefix="/api")


def _validar_coordenadas(lat: Any, lng: Any, accuracy: Any) -> tuple[float, float, float | None] | None:
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat_f <= 90) or not (-180 <= lng_f <= 180):
        return None
    acc = None
    if accuracy is not None and accuracy != "":
        try:
            acc = float(accuracy)
        except (TypeError, ValueError):
            return None
        if acc < 0:
            return None
    return lat_f, lng_f, acc


@api_ubicacion_bp.route("/ubicacion/actualizar", methods=["POST"])
@login_required
def actualizar_ubicacion() -> Any:
    """Cliente autenticado envía su posición GPS en vivo para una cita activa."""
    data = request.get_json(silent=True) or {}
    cita_id = data.get("cita_id")

    cliente = PortalService.get_cliente_de_usuario(current_user)
    if cliente is None:
        return json_error("El usuario no está asociado a un cliente del taller.", status=403)

    coords = _validar_coordenadas(
        data.get("latitude"), data.get("longitude"), data.get("accuracy")
    )
    if coords is None:
        return json_error("Coordenadas inválidas. Revisa el permiso de ubicación.", status=400)

    lat, lng, acc = coords
    try:
        registro = UbicacionService.actualizar(
            cliente_id=cliente.id,
            cita_id=int(cita_id) if cita_id else None,
            latitude=lat,
            longitude=lng,
            accuracy=acc,
        )
    except UbicacionError as e:
        return json_error(str(e), status=400)
    except (TypeError, ValueError):
        return json_error("Identificador de cita inválido.", status=400)

    try:
        safe_commit(fail_msg="Ubicación no actualizada")
    except Exception:
        db.session.rollback()
        return json_error("No se pudo guardar la ubicación. Intenta nuevamente.")

    logger.info(
        "Cliente %s comparte ubicación para cita %s", cliente.id, registro.cita_id
    )
    return json_success(
        {
            "ubicacion_id": registro.id,
            "cita_id": registro.cita_id,
            "sharing_active": registro.sharing_active,
        },
        "Ubicación actualizada correctamente.",
    )


@api_ubicacion_bp.route("/ubicacion/detener", methods=["POST"])
@login_required
def detener_ubicacion() -> Any:
    """El cliente deja de compartir su ubicación (privacidad)."""
    cliente = PortalService.get_cliente_de_usuario(current_user)
    if cliente is None:
        return json_error("El usuario no está asociado a un cliente del taller.", status=403)

    data = request.get_json(silent=True) or {}
    cita_id = data.get("cita_id")
    try:
        cita_id_int = int(cita_id) if cita_id else None
    except (TypeError, ValueError):
        return json_error("Identificador de cita inválido.", status=400)

    apagadas = UbicacionService.detener(cliente.id, cita_id_int)
    try:
        safe_commit(fail_msg="No se pudo detener el intercambio")
    except Exception:
        db.session.rollback()
        return json_error("No se pudo detener el intercambio de ubicación.")

    logger.info("Cliente %s detuvo el compartido de ubicación", cliente.id)
    return json_success(
        {"apagadas": apagadas, "sharing_active": False},
        "Ya dejaste de compartir tu ubicación.",
    )


@api_ubicacion_bp.route("/ubicacion/estado")
@login_required
def estado_ubicacion() -> Any:
    """Estado actual (cita activa + compartidos) para el portal del cliente."""
    cliente = PortalService.get_cliente_de_usuario(current_user)
    if cliente is None:
        return json_error("El usuario no está asociado a un cliente del taller.", status=403)
    return json_success(UbicacionService.estado_para_portal(cliente))


@api_ubicacion_bp.route("/admin/clientes-en-camino")
@login_required
@staff_required
def clientes_en_camino() -> Any:
    """Solo staff: lista de clientes en camino con distancia/ETA reales."""
    return json_success(UbicacionService.clientes_en_camino())