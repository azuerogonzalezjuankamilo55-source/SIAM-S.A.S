import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from models import Usuario
from database.db import db
from forms import LoginForm, RegisterForm

logger = logging.getLogger("siam.routes.auth")
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

limiter = Limiter(key_func=get_remote_address)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10/minute")
def login() -> Any:
    form = LoginForm()
    if form.validate_on_submit():
        correo = form.correo.data
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
        correo = form.correo.data
        if Usuario.query.filter_by(correo=correo).first():
            flash("El correo ya está registrado", "danger")
            return render_template("auth/register.html", form=form)
        usuario = Usuario(
            nombre=form.nombre.data,
            correo=correo,
        )
        usuario.set_password(form.password.data)
        db.session.add(usuario)
        db.session.commit()
        logger.info("Nuevo usuario registrado: %s", correo)
        flash("Registro exitoso. Inicia sesión.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)
