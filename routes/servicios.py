import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required
from flask_wtf.csrf import validate_csrf

from models.servicio import Servicio
from database.db import db
from database.commit import safe_commit, json_success, json_error
from forms import ServicioForm
from exceptions import BusinessRuleException
from services.image_service import ImageService, ImageError
from decorators import staff_blueprint_guard

logger = logging.getLogger("siam.routes.servicios")
servicios_bp = Blueprint("servicios", __name__, url_prefix="/servicios")
servicios_bp.before_request(staff_blueprint_guard)


def _procesar_imagen(form, servicio) -> None:
    archivo = getattr(form, "imagen", None)
    if not archivo or not archivo.data or not getattr(archivo.data, "filename", ""):
        return
    try:
        nueva = ImageService.guardar(archivo.data, "servicios")
    except ImageError as e:
        raise BusinessRuleException(str(e))
    vieja = servicio.imagen_path
    servicio.imagen_path = nueva
    if vieja:
        ImageService.eliminar(vieja)


@servicios_bp.route("/")
@login_required
def listar() -> Any:
    servicios = Servicio.query.order_by(Servicio.nombre).all()
    return render_template("servicios/listar.html", servicios=servicios)


@servicios_bp.route("/crear", methods=["GET", "POST"])
@login_required
def crear() -> Any:
    form = ServicioForm()
    if form.validate_on_submit():
        try:
            servicio = Servicio(
                nombre=form.nombre.data,
                descripcion=form.descripcion.data,
                precio_estimado=form.precio_estimado.data,
                duracion_estimada=form.duracion_estimada.data,
                categoria=form.categoria.data,
            )
            _procesar_imagen(form, servicio)
            db.session.add(servicio)
            safe_commit()
            logger.info("Servicio creado: %s", servicio.nombre)
            if request.is_json:
                return json_success(message="Creado correctamente.")
            flash("Servicio creado", "success")
            return redirect(url_for("servicios.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template("servicios/form.html", form=form)


@servicios_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id: int) -> Any:
    servicio = db.get_or_404(Servicio, id)
    form = ServicioForm(obj=servicio)
    if form.validate_on_submit():
        try:
            form.populate_obj(servicio)
            _procesar_imagen(form, servicio)
            safe_commit()
            logger.info("Servicio actualizado: %s", servicio.nombre)
            if request.is_json:
                return json_success(message="Actualizado correctamente.")
            flash("Servicio actualizado", "success")
            return redirect(url_for("servicios.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template("servicios/form.html", form=form, servicio=servicio)


@servicios_bp.route("/eliminar/<int:id>", methods=["POST"])
@login_required
def eliminar(id: int) -> Any:
    try:
        csrf_token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if csrf_token:
            validate_csrf(csrf_token)
    except Exception:
        if request.is_json:
            return json_error(message="CSRF invÃ¡lido"), 403
        flash("Error de validaciÃ³n. Intenta de nuevo.", "danger")
        return redirect(url_for("servicios.listar"))
    try:
        servicio = db.get_or_404(Servicio, id)
        db.session.delete(servicio)
        safe_commit("No se pudo eliminar.")
        logger.info("Servicio eliminado: %s", servicio.nombre)
        if request.is_json:
            return json_success(message="Eliminado correctamente.")
        flash("Servicio eliminado", "success")
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("servicios.listar"))
