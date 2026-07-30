import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required

from models.cita import Cita
from models.cliente import Cliente
from models.vehiculo import Vehiculo
from models.mecanico import Mecanico
from database.db import db
from database.commit import safe_commit, json_success, json_error
from forms import CitaForm

logger = logging.getLogger("siam.routes.citas")
citas_bp = Blueprint("citas", __name__, url_prefix="/citas")


@citas_bp.route("/")
@login_required
def listar() -> Any:
    citas = Cita.query.order_by(Cita.fecha.desc(), Cita.hora.desc()).all()
    return render_template("citas/listar.html", citas=citas)


@citas_bp.route("/crear", methods=["GET", "POST"])
@login_required
def crear() -> Any:
    form = CitaForm()
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    vehiculos = Vehiculo.query.order_by(Vehiculo.placa).all()
    mecanicos = Mecanico.query.filter_by(activo=True).order_by(Mecanico.nombre).all()
    if form.validate_on_submit():
        try:
            cita = Cita(
                cliente_id=form.cliente_id.data,
                vehiculo_id=form.vehiculo_id.data,
                mecanico_id=form.mecanico_id.data or None,
                fecha=form.fecha.data,
                hora=form.hora.data,
                descripcion=form.descripcion.data,
            )
            db.session.add(cita)
            safe_commit()
            logger.info("Cita creada: #%s para cliente %s", cita.id, cita.cliente_id)
            if request.is_json:
                return json_success(message="Creada correctamente.")
            flash("Cita agendada", "success")
            return redirect(url_for("citas.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template("citas/form.html", form=form, clientes=clientes, vehiculos=vehiculos, mecanicos=mecanicos)


@citas_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id: int) -> Any:
    cita = Cita.query.get_or_404(id)
    form = CitaForm(obj=cita)
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    vehiculos = Vehiculo.query.order_by(Vehiculo.placa).all()
    mecanicos = Mecanico.query.filter_by(activo=True).order_by(Mecanico.nombre).all()
    if form.validate_on_submit():
        try:
            form.populate_obj(cita)
            safe_commit()
            logger.info("Cita actualizada: #%s", cita.id)
            if request.is_json:
                return json_success(message="Actualizada correctamente.")
            flash("Cita actualizada", "success")
            return redirect(url_for("citas.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template("citas/form.html", form=form, cita=cita, clientes=clientes, vehiculos=vehiculos, mecanicos=mecanicos)


@citas_bp.route("/eliminar/<int:id>")
@login_required
def eliminar(id: int) -> Any:
    try:
        cita = Cita.query.get_or_404(id)
        db.session.delete(cita)
        safe_commit("No se pudo eliminar.")
        logger.info("Cita eliminada: #%s", id)
        if request.is_json:
            return json_success(message="Eliminada correctamente.")
        flash("Cita eliminada", "success")
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("citas.listar"))


@citas_bp.route("/cambiar-estado/<int:id>/<estado>")
@login_required
def cambiar_estado(id: int, estado: str) -> Any:
    try:
        cita = Cita.query.get_or_404(id)
        estados_validos = ("pendiente", "en_proceso", "completado", "cancelado")
        if estado in estados_validos:
            cita.estado = estado
            safe_commit()
            logger.info("Cita #%s cambió a estado: %s", id, estado)
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("citas.listar"))


@citas_bp.route("/obtener-vehiculos/<int:cliente_id>")
@login_required
def obtener_vehiculos(cliente_id: int) -> Any:
    vehiculos = Vehiculo.query.filter_by(cliente_id=cliente_id).all()
    return jsonify([
        {"id": v.id, "texto": f"{v.marca} {v.modelo} - {v.placa}"}
        for v in vehiculos
    ])
