import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required
from flask_wtf.csrf import validate_csrf

from models.vehiculo import Vehiculo
from models.cliente import Cliente
from database.db import db
from forms import VehiculoForm
from database.commit import safe_commit, json_success, json_error

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
        try:
            safe_commit()
            logger.info("Vehículo registrado: %s %s", vehiculo.marca, vehiculo.placa)
            if request.is_json:
                return jsonify({"success": True, "message": "Vehículo registrado"})
            flash("Vehículo registrado", "success")
            return redirect(url_for("vehiculos.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(str(e))
            flash(str(e), "danger")
            return render_template("vehiculos/form.html", form=form, clientes=clientes)
    return render_template("vehiculos/form.html", form=form, clientes=clientes)


@vehiculos_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id: int) -> Any:
    vehiculo = Vehiculo.query.get_or_404(id)
    form = VehiculoForm(obj=vehiculo)
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    if form.validate_on_submit():
        form.populate_obj(vehiculo)
        try:
            safe_commit()
            logger.info("Vehículo actualizado: %s", vehiculo.placa)
            if request.is_json:
                return jsonify({"success": True, "message": "Vehículo actualizado"})
            flash("Vehículo actualizado", "success")
            return redirect(url_for("vehiculos.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(str(e))
            flash(str(e), "danger")
            return render_template("vehiculos/form.html", form=form, vehiculo=vehiculo, clientes=clientes)
    return render_template("vehiculos/form.html", form=form, vehiculo=vehiculo, clientes=clientes)


@vehiculos_bp.route("/eliminar/<int:id>", methods=["POST"])
@login_required
def eliminar(id: int) -> Any:
    try:
        csrf_token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if csrf_token:
            validate_csrf(csrf_token)
    except Exception:
        if request.is_json:
            return jsonify({"error": "CSRF inválido"}), 403
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("vehiculos.listar"))
    vehiculo = Vehiculo.query.get_or_404(id)
    db.session.delete(vehiculo)
    try:
        safe_commit()
        logger.info("Vehículo eliminado: %s", vehiculo.placa)
        if request.is_json:
            return jsonify({"success": True})
        flash("Vehículo eliminado", "success")
        return redirect(url_for("vehiculos.listar"))
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(str(e))
        flash(str(e), "danger")
        return redirect(url_for("vehiculos.listar"))
