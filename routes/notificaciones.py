import logging

from flask import Blueprint, jsonify, request, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from database.commit import json_success, json_error
from models.notificacion import TIPOS_NOTIFICACION, TIPOS_NOTIFICACION_LABELS
from services.notification_service import NotificationService

logger = logging.getLogger("siam.routes.notificaciones")
notificaciones_bp = Blueprint("notificaciones", __name__, url_prefix="/notificaciones")


@notificaciones_bp.route("/")
@login_required
def index():
    tipo = request.args.get("tipo") or ""
    solo_no_leidas = request.args.get("pendientes") == "1"
    if tipo not in TIPOS_NOTIFICACION:
        tipo = ""
    items = NotificationService.list_all(
        current_user.id, tipo=tipo or None, solo_no_leidas=solo_no_leidas
    )
    no_leidas = NotificationService.unread_count(current_user.id)
    por_tipo = {}
    todas = NotificationService.list_all(current_user.id, limit=1000)
    for n in todas:
        por_tipo[n.tipo] = por_tipo.get(n.tipo, 0) + 1
    return render_template(
        "notificaciones/index.html",
        items=items,
        filtro_tipo=tipo,
        solo_no_leidas=solo_no_leidas,
        no_leidas=no_leidas,
        tipos=TIPOS_NOTIFICACION,
        tipos_labels=TIPOS_NOTIFICACION_LABELS,
        por_tipo=por_tipo,
    )


@notificaciones_bp.route("/eliminar/<int:notificacion_id>", methods=["POST"])
@login_required
def eliminar(notificacion_id: int):
    try:
        if NotificationService.eliminar(current_user.id, notificacion_id):
            if request.is_json:
                return json_success({"id": notificacion_id}, "Notificación eliminada.")
            flash("Notificación eliminada.", "success")
            return redirect(url_for("notificaciones.index"))
        if request.is_json:
            return json_error("Notificación no encontrada.", status=404)
        flash("Notificación no encontrada.", "danger")
        return redirect(url_for("notificaciones.index"))
    except Exception as e:
        logger.error("Error al eliminar notificación: %s", e)
        if request.is_json:
            return json_error()
        flash("No se pudo eliminar la notificación.", "danger")
        return redirect(url_for("notificaciones.index"))


@notificaciones_bp.route("/api/no-leidas")
@login_required
def api_no_leidas():
    return jsonify({"count": NotificationService.unread_count(current_user.id)})


@notificaciones_bp.route("/api/listar")
@login_required
def api_listar():
    limite = min(int(request.args.get("limite", 20)), 50)
    items = NotificationService.list_for(current_user.id, limit=limite)
    return jsonify({
        "items": [NotificationService.to_dict(n) for n in items],
        "count": len(items),
    })


@notificaciones_bp.route("/api/leer/<int:notificacion_id>", methods=["POST"])
@login_required
def api_leer(notificacion_id: int):
    try:
        if NotificationService.mark_read(current_user.id, notificacion_id):
            return json_success({"id": notificacion_id}, "Notificación marcada como leída.")
        return json_error("Notificación no encontrada.", status=404)
    except Exception as e:
        logger.error("Error al marcar notificación: %s", e)
        return json_error()


@notificaciones_bp.route("/api/leer-todas", methods=["POST"])
@login_required
def api_leer_todas():
    try:
        count = NotificationService.mark_all_read(current_user.id)
        return json_success({"marcadas": count}, "Todas las notificaciones fueron leídas.")
    except Exception as e:
        logger.error("Error al marcar todas las notificaciones: %s", e)
        return json_error()
