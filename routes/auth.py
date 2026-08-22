import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user

from models import Usuario, Cliente
from database.db import db
from forms import LoginForm, RegisterForm
from database.commit import safe_commit, json_success, json_error

logger = logging.getLogger("siam.routes.auth")
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login() -> Any:
    if current_user.is_authenticated:
        if current_user.es_cliente:
            return redirect(url_for("portal.index"))
        return redirect(url_for("dashboard.index"))
    form = LoginForm()
    if form.validate_on_submit():
        correo = form.correo.data.strip().lower()
        password = form.password.data
        usuario: Usuario | None = Usuario.query.filter_by(correo=correo).first()
        if usuario and usuario.check_password(password):
            if not usuario.activo:
                flash("Tu cuenta está desactivada. Contacta al administrador.", "danger")
                return render_template("auth/login.html", form=form)
            login_user(usuario)
            logger.info("Login exitoso: %s", correo)
            try:
                from datetime import datetime
                usuario.last_access_at = datetime.now()
                safe_commit()
            except Exception as e:
                logger.warning("No se pudo registrar último acceso: %s", e)
            if usuario.es_cliente:
                return redirect(url_for("portal.index"))
            return redirect(url_for("dashboard.index"))
        logger.warning("Intento de login fallido: %s", correo)
        flash("Credenciales inválidas", "danger")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout() -> Any:
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register() -> Any:
    if current_user.is_authenticated:
        if current_user.es_cliente:
            return redirect(url_for("portal.index"))
        return redirect(url_for("dashboard.index"))
    form = RegisterForm()
    if form.validate_on_submit():
        correo = form.correo.data.strip().lower()
        if Usuario.query.filter_by(correo=correo).first():
            if request.is_json:
                return jsonify({"success": False, "error": "El correo ya está registrado"}), 400
            flash("El correo ya está registrado", "danger")
            return render_template("auth/register.html", form=form)
        cliente = Cliente.query.filter(db.func.lower(Cliente.correo) == correo).first()
        usuario = Usuario(
            nombre=form.nombre.data.strip(),
            correo=correo,
            rol="cliente",
            cliente_id=cliente.id if cliente else None,
        )
        usuario.set_password(form.password.data)
        if not cliente and correo:
            nuevo_cliente = Cliente(
                nombre=form.nombre.data.strip(),
                correo=correo,
            )
            db.session.add(nuevo_cliente)
            db.session.flush()
            usuario.cliente_id = nuevo_cliente.id
        db.session.add(usuario)
        try:
            safe_commit()
            logger.info("Nuevo usuario cliente registrado: %s", correo)
            if request.is_json:
                return jsonify({"success": True, "message": "Registro exitoso. Inicia sesión."})
            flash("Registro exitoso. Inicia sesión.", "success")
            return redirect(url_for("auth.login"))
        except Exception:
            db.session.rollback()
            logger.exception("Error registrando usuario %s", correo)
            mensaje = "No se pudo completar el registro. Intenta nuevamente."
            if request.is_json:
                return json_error(mensaje)
            flash(mensaje, "danger")
            return render_template("auth/register.html", form=form)
    return render_template("auth/register.html", form=form)
