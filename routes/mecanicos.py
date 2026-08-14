import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required
from flask_wtf.csrf import validate_csrf

from models.mecanico import Mecanico
from database.db import db
from database.commit import safe_commit, json_success, json_error
from forms import MecanicoForm
from exceptions import BusinessRuleException
from services.image_service import ImageService, ImageError
from decorators import staff_blueprint_guard

logger = logging.getLogger("siam.routes.mecanicos")
mecanicos_bp = Blueprint("mecanicos", __name__, url_prefix="/mecanicos")
mecanicos_bp.before_request(staff_blueprint_guard)


def _procesar_foto(form, mecanico) -> None:
    archivo = getattr(form, "foto", None)
    if not archivo or not archivo.data or not getattr(archivo.data, "filename", ""):
        return
    try:
        nueva = ImageService.guardar(archivo.data, "mecanicos")
    except ImageError as e:
        raise BusinessRuleException(str(e))
    vieja = mecanico.foto_path
    mecanico.foto_path = nueva
    if vieja:
        ImageService.eliminar(vieja)


@mecanicos_bp.route("/")
@login_required
def listar() -> Any:
    mecanicos = Mecanico.query.order_by(Mecanico.nombre).all()
    return render_template("mecanicos/listar.html", mecanicos=mecanicos)


@mecanicos_bp.route("/crear", methods=["GET", "POST"])
@login_required
def crear() -> Any:
    form = MecanicoForm()
    if form.validate_on_submit():
        try:
            mecanico = Mecanico(
                nombre=form.nombre.data,
                telefono=form.telefono.data,
                correo=form.correo.data,
                especialidad=form.especialidad.data,
            )
            _procesar_foto(form, mecanico)
            db.session.add(mecanico)
            safe_commit()
            logger.info("MecÃ¡nico creado: %s", mecanico.nombre)
            if request.is_json:
                return json_success(message="Creado correctamente.")
            flash("MecÃ¡nico registrado", "success")
            return redirect(url_for("mecanicos.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template("mecanicos/form.html", form=form)


@mecanicos_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id: int) -> Any:
    mecanico = db.get_or_404(Mecanico, id)
    form = MecanicoForm(obj=mecanico)
    if form.validate_on_submit():
        try:
            form.populate_obj(mecanico)
            _procesar_foto(form, mecanico)
            safe_commit()
            logger.info("MecÃ¡nico actualizado: %s", mecanico.nombre)
            if request.is_json:
                return json_success(message="Actualizado correctamente.")
            flash("MecÃ¡nico actualizado", "success")
            return redirect(url_for("mecanicos.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template("mecanicos/form.html", form=form, mecanico=mecanico)


@mecanicos_bp.route("/eliminar/<int:id>", methods=["POST"])
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
        return redirect(url_for("mecanicos.listar"))
    try:
        mecanico = db.get_or_404(Mecanico, id)
        db.session.delete(mecanico)
        safe_commit("No se pudo eliminar.")
        logger.info("MecÃ¡nico eliminado: %s", mecanico.nombre)
        if request.is_json:
            return json_success(message="Eliminado correctamente.")
        flash("MecÃ¡nico eliminado", "success")
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("mecanicos.listar"))
