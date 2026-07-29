import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required

from models.vehiculo import Vehiculo
from models.cliente import Cliente
from database.db import db
from forms import VehiculoForm

logger = logging.getLogger("siam.routes.vehiculos")
vehiculos_bp = Blueprint("vehiculos", __name__, url_prefix="/vehiculos")


@vehiculos_bp.route("/")
@login_required
def listar() -> Any:
    vehiculos = Vehiculo.query.order_by(Vehiculo.created_at.desc()).all()
    return render_template("vehiculos/listar.html", vehiculos=vehiculos)


@vehiculos_bp.route("/crear", methods=["GET", "POST"])
@login_required
def crear() -> Any:
    form = VehiculoForm()
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    if form.validate_on_submit():
        vehiculo = Vehiculo(
            cliente_id=form.cliente_id.data,
            marca=form.marca.data,
            modelo=form.modelo.data,
            anio=form.anio.data,
            placa=form.placa.data,
            vin=form.vin.data,
            color=form.color.data,
        )
        db.session.add(vehiculo)
        db.session.commit()
        logger.info("Vehículo registrado: %s %s", vehiculo.marca, vehiculo.placa)
        flash("Vehículo registrado", "success")
        return redirect(url_for("vehiculos.listar"))
    return render_template("vehiculos/form.html", form=form, clientes=clientes)


@vehiculos_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id: int) -> Any:
    vehiculo = Vehiculo.query.get_or_404(id)
    form = VehiculoForm(obj=vehiculo)
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    if form.validate_on_submit():
        form.populate_obj(vehiculo)
        db.session.commit()
        logger.info("Vehículo actualizado: %s", vehiculo.placa)
        flash("Vehículo actualizado", "success")
        return redirect(url_for("vehiculos.listar"))
    return render_template("vehiculos/form.html", form=form, vehiculo=vehiculo, clientes=clientes)


@vehiculos_bp.route("/eliminar/<int:id>")
@login_required
def eliminar(id: int) -> Any:
    vehiculo = Vehiculo.query.get_or_404(id)
    db.session.delete(vehiculo)
    db.session.commit()
    logger.info("Vehículo eliminado: %s", vehiculo.placa)
    flash("Vehículo eliminado", "success")
    return redirect(url_for("vehiculos.listar"))
