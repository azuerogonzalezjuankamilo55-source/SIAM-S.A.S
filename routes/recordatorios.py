import logging
from datetime import date
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash

from database.db import db
from database.commit import safe_commit
from decorators import admin_required, staff_blueprint_guard
from models import Vehiculo, Recordatorio, ESTADOS_RECORDATORIO, TIPOS_RECORDATORIO
from services.recordatorio_service import RecordatorioService

logger = logging.getLogger("siam.routes.recordatorios")
recordatorios_bp = Blueprint("recordatorios", __name__, url_prefix="/recordatorios")
recordatorios_bp.before_request(staff_blueprint_guard)


@recordatorios_bp.route("/")
@admin_required
def index() -> Any:
    estado = request.args.get("estado") or ""
    tipo = request.args.get("tipo") or ""
    if estado not in ESTADOS_RECORDATORIO:
        estado = ""
    if tipo not in TIPOS_RECORDATORIO:
        tipo = ""
    lista = RecordatorioService.get_todos(estado=estado or None, tipo=tipo or None)
    vehiculos = Vehiculo.query.order_by(Vehiculo.placa).all()
    pendientes = Recordatorio.query.filter_by(estado="pendiente").count()
    return render_template(
        "recordatorios/index.html",
        recordatorios=lista,
        vehiculos=vehiculos,
        filtro_estado=estado,
        filtro_tipo=tipo,
        pendientes=pendientes,
    )


@recordatorios_bp.route("/generar", methods=["POST"])
@admin_required
def generar() -> Any:
    try:
        creados = RecordatorioService.generar_mantenimientos()
    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")
        return redirect(url_for("recordatorios.index"))
    flash(f"Se generaron {creados} recordatorios de mantenimiento.", "success" if creados else "info")
    return redirect(url_for("recordatorios.index"))


@recordatorios_bp.route("/crear", methods=["POST"])
@admin_required
def crear() -> Any:
    vehiculo_id = request.form.get("vehiculo_id", type=int)
    titulo = (request.form.get("titulo") or "").strip()
    descripcion = request.form.get("descripcion")
    fecha_raw = request.form.get("fecha_programada")
    canal = request.form.get("canal") or "portal"
    if not vehiculo_id or not titulo or not fecha_raw:
        flash("Completa vehículo, título y fecha.", "danger")
        return redirect(url_for("recordatorios.index"))
    try:
        fecha = date.fromisoformat(fecha_raw)
    except ValueError:
        flash("Fecha inválida.", "danger")
        return redirect(url_for("recordatorios.index"))
    try:
        RecordatorioService.crear_manual(vehiculo_id, titulo, descripcion, fecha, canal=canal)
    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")
        return redirect(url_for("recordatorios.index"))
    flash("Recordatorio creado.", "success")
    return redirect(url_for("recordatorios.index"))


@recordatorios_bp.route("/<int:recordatorio_id>/estado/<estado>", methods=["POST"])
@admin_required
def cambiar_estado(recordatorio_id: int, estado: str) -> Any:
    try:
        recordatorio = RecordatorioService.cambiar_estado(recordatorio_id, estado)
    except ValueError:
        flash("Estado inválido.", "danger")
        return redirect(url_for("recordatorios.index"))
    if not recordatorio:
        flash("Recordatorio no encontrado.", "danger")
        return redirect(url_for("recordatorios.index"))
    flash(f"Recordatorio marcado como {recordatorio.estado_label}.", "success")
    return redirect(request.referrer or url_for("recordatorios.index"))
