import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required
from flask_wtf.csrf import validate_csrf

from models.cliente import Cliente
from database.db import db
from forms import ClienteForm
from database.commit import safe_commit, json_success, json_error
from decorators import staff_blueprint_guard, roles_required

logger = logging.getLogger("siam.routes.clientes")
clientes_bp = Blueprint("clientes", __name__, url_prefix="/clientes")
clientes_bp.before_request(staff_blueprint_guard)


@clientes_bp.route("/")
@login_required
@roles_required("admin", "recepcion")
def listar() -> Any:
    clientes = Cliente.query.order_by(Cliente.created_at.desc()).all()
    return render_template("clientes/listar.html", clientes=clientes)


@clientes_bp.route("/crear", methods=["GET", "POST"])
@login_required
@roles_required("admin", "recepcion")
def crear() -> Any:
    form = ClienteForm()
    if form.validate_on_submit():
        cliente = Cliente(
            nombre=form.nombre.data.strip(),
            telefono=form.telefono.data.strip() if form.telefono.data else None,
            correo=form.correo.data.strip() if form.correo.data else None,
            direccion=form.direccion.data.strip() if form.direccion.data else None,
            cedula=form.cedula.data.strip() if form.cedula.data else None,
        )
        db.session.add(cliente)
        try:
            safe_commit()
            logger.info("Cliente creado: %s", cliente.nombre)
            if request.is_json:
                return jsonify({"success": True, "message": "Cliente creado exitosamente"})
            flash("Cliente creado exitosamente", "success")
            return redirect(url_for("clientes.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(str(e))
            flash(str(e), "danger")
            return render_template("clientes/form.html", form=form)
    return render_template("clientes/form.html", form=form)


@clientes_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
@roles_required("admin", "recepcion")
def editar(id: int) -> Any:
    cliente = db.get_or_404(Cliente, id)
    form = ClienteForm(obj=cliente)
    if form.validate_on_submit():
        form.populate_obj(cliente)
        try:
            safe_commit()
            logger.info("Cliente actualizado: %s", cliente.nombre)
            if request.is_json:
                return jsonify({"success": True, "message": "Cliente actualizado"})
            flash("Cliente actualizado", "success")
            return redirect(url_for("clientes.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(str(e))
            flash(str(e), "danger")
            return render_template("clientes/form.html", form=form, cliente=cliente)
    return render_template("clientes/form.html", form=form, cliente=cliente)


@clientes_bp.route("/eliminar/<int:id>", methods=["POST"])
@login_required
@roles_required("admin")
def eliminar(id: int) -> Any:
    try:
        csrf_token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if csrf_token:
            validate_csrf(csrf_token)
    except Exception:
        if request.is_json:
            return jsonify({"error": "CSRF inválido"}), 403
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("clientes.listar"))
    cliente = db.get_or_404(Cliente, id)
    db.session.delete(cliente)
    try:
        safe_commit()
        logger.info("Cliente eliminado: %s", cliente.nombre)
        if request.is_json:
            return jsonify({"success": True})
        flash("Cliente eliminado", "success")
        return redirect(url_for("clientes.listar"))
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(str(e))
        flash(str(e), "danger")
        return redirect(url_for("clientes.listar"))
