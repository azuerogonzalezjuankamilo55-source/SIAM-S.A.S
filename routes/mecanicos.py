import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required

from models.mecanico import Mecanico
from database.db import db
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
        mecanico = Mecanico(
            nombre=form.nombre.data,
            telefono=form.telefono.data,
            correo=form.correo.data,
            especialidad=form.especialidad.data,
        )
        db.session.add(mecanico)
        db.session.commit()
        logger.info("Mecánico creado: %s", mecanico.nombre)
        flash("Mecánico registrado", "success")
        return redirect(url_for("mecanicos.listar"))
    return render_template("mecanicos/form.html", form=form)


@mecanicos_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id: int) -> Any:
    mecanico = Mecanico.query.get_or_404(id)
    form = MecanicoForm(obj=mecanico)
    if form.validate_on_submit():
        form.populate_obj(mecanico)
        db.session.commit()
        logger.info("Mecánico actualizado: %s", mecanico.nombre)
        flash("Mecánico actualizado", "success")
        return redirect(url_for("mecanicos.listar"))
    return render_template("mecanicos/form.html", form=form, mecanico=mecanico)


@mecanicos_bp.route("/eliminar/<int:id>")
@login_required
def eliminar(id: int) -> Any:
    mecanico = Mecanico.query.get_or_404(id)
    db.session.delete(mecanico)
    db.session.commit()
    logger.info("Mecánico eliminado: %s", mecanico.nombre)
    flash("Mecánico eliminado", "success")
    return redirect(url_for("mecanicos.listar"))
