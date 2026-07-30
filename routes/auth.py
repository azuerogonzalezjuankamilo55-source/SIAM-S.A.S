import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, logout_user, login_required

from models import Usuario
from database.db import db
from forms import LoginForm, RegisterForm
from database.commit import safe_commit, json_success, json_error

logger = logging.getLogger("siam.routes.auth")
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login() -> Any:
    form = LoginForm()
    if form.validate_on_submit():
        correo = form.correo.data.strip().lower()
        password = form.password.data
        usuario: Usuario | None = Usuario.query.filter_by(correo=correo).first()
        if usuario and usuario.check_password(password):
            login_user(usuario)
            logger.info("Login exitoso: %s", correo)
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
    form = RegisterForm()
    if form.validate_on_submit():
        correo = form.correo.data.strip().lower()
        if Usuario.query.filter_by(correo=correo).first():
            if request.is_json:
                return jsonify({"success": False, "error": "El correo ya está registrado"}), 400
            flash("El correo ya está registrado", "danger")
            return render_template("auth/register.html", form=form)
        usuario = Usuario(
            nombre=form.nombre.data.strip(),
            correo=correo,
        )
        usuario.set_password(form.password.data)
        db.session.add(usuario)
        try:
            safe_commit()
            logger.info("Nuevo usuario registrado: %s", correo)
            if request.is_json:
                return jsonify({"success": True, "message": "Registro exitoso. Inicia sesión."})
            flash("Registro exitoso. Inicia sesión.", "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(str(e))
            flash(str(e), "danger")
            return render_template("auth/register.html", form=form)
    return render_template("auth/register.html", form=form)
