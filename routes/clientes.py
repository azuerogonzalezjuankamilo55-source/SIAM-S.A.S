import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required

from models.cliente import Cliente
from database.db import db
from forms import ClienteForm

logger = logging.getLogger("siam.routes.clientes")
clientes_bp = Blueprint("clientes", __name__, url_prefix="/clientes")


@clientes_bp.route("/")
@login_required
def listar() -> Any:
    clientes = Cliente.query.order_by(Cliente.created_at.desc()).all()
    return render_template("clientes/listar.html", clientes=clientes)


@clientes_bp.route("/crear", methods=["GET", "POST"])
@login_required
def crear() -> Any:
    form = ClienteForm()
    if form.validate_on_submit():
        cliente = Cliente(
            nombre=form.nombre.data,
            telefono=form.telefono.data,
            correo=form.correo.data,
            direccion=form.direccion.data,
            cedula=form.cedula.data,
        )
        db.session.add(cliente)
        db.session.commit()
        logger.info("Cliente creado: %s", cliente.nombre)
        flash("Cliente creado exitosamente", "success")
        return redirect(url_for("clientes.listar"))
    return render_template("clientes/form.html", form=form)


@clientes_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id: int) -> Any:
    cliente = Cliente.query.get_or_404(id)
    form = ClienteForm(obj=cliente)
    if form.validate_on_submit():
        form.populate_obj(cliente)
        db.session.commit()
        logger.info("Cliente actualizado: %s", cliente.nombre)
        flash("Cliente actualizado", "success")
        return redirect(url_for("clientes.listar"))
    return render_template("clientes/form.html", form=form, cliente=cliente)


@clientes_bp.route("/eliminar/<int:id>")
@login_required
def eliminar(id: int) -> Any:
    cliente = Cliente.query.get_or_404(id)
    db.session.delete(cliente)
    db.session.commit()
    logger.info("Cliente eliminado: %s", cliente.nombre)
    flash("Cliente eliminado", "success")
    return redirect(url_for("clientes.listar"))
