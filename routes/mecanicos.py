import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required
from flask_wtf.csrf import validate_csrf

from models.mecanico import Mecanico
from database.db import db
from database.commit import safe_commit, json_success, json_error
from forms import MecanicoForm

logger = logging.getLogger("siam.routes.mecanicos")
mecanicos_bp = Blueprint("mecanicos", __name__, url_prefix="/mecanicos")


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
            db.session.add(mecanico)
            safe_commit()
            logger.info("Mecánico creado: %s", mecanico.nombre)
            if request.is_json:
                return json_success(message="Creado correctamente.")
            flash("Mecánico registrado", "success")
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
    mecanico = Mecanico.query.get_or_404(id)
    form = MecanicoForm(obj=mecanico)
    if form.validate_on_submit():
        try:
            form.populate_obj(mecanico)
            safe_commit()
            logger.info("Mecánico actualizado: %s", mecanico.nombre)
            if request.is_json:
                return json_success(message="Actualizado correctamente.")
            flash("Mecánico actualizado", "success")
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
            return json_error(message="CSRF inválido"), 403
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("mecanicos.listar"))
    try:
        mecanico = Mecanico.query.get_or_404(id)
        db.session.delete(mecanico)
        safe_commit("No se pudo eliminar.")
        logger.info("Mecánico eliminado: %s", mecanico.nombre)
        if request.is_json:
            return json_success(message="Eliminado correctamente.")
        flash("Mecánico eliminado", "success")
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("mecanicos.listar"))
