import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user

from models import Usuario, Cliente
from database.db import db
from forms import LoginForm, RegisterForm, AdminRegisterForm
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
    area = request.args.get("area") or ""
    if area not in ("admin", "cliente"):
        area = ""
    if form.validate_on_submit():
        correo = form.correo.data.strip().lower()
        password = form.password.data
        usuario: Usuario | None = Usuario.query.filter_by(correo=correo).first()
        if usuario and usuario.check_password(password):
            if not usuario.activo:
                flash("Tu cuenta está desactivada. Contacta al administrador.", "danger")
                return render_template("auth/login.html", form=form, area=area)
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
    return render_template("auth/login.html", form=form, area=area)


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
        documento = form.documento.data.strip()
        if Usuario.query.filter_by(correo=correo).first():
            if request.is_json:
                return jsonify({"success": False, "error": "El correo ya está registrado"}), 400
            flash("El correo ya está registrado", "danger")
            return render_template("auth/register.html", form=form)
        cliente = Cliente.query.filter(db.func.lower(Cliente.correo) == correo).first()
        por_documento = Cliente.query.filter(Cliente.cedula == documento).first() if documento else None
        # Un documento ya usado solo es válido si pertenece al mismo cliente
        # (vinculación por correo); nunca permite tomar registros ajenos.
        if por_documento and (not cliente or por_documento.id != cliente.id):
            if not cliente and por_documento and not por_documento.correo:
                cliente = por_documento
            elif por_documento:
                if request.is_json:
                    return jsonify({"success": False, "error": "Ese documento ya está registrado"}), 400
                flash("Ese documento ya está registrado", "danger")
                return render_template("auth/register.html", form=form)
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
                cedula=documento or None,
                telefono=(form.telefono.data or "").strip() or None,
            )
            db.session.add(nuevo_cliente)
            db.session.flush()
            usuario.cliente_id = nuevo_cliente.id
        elif cliente and documento:
            if not cliente.cedula:
                cliente.cedula = documento
            if form.telefono.data and not cliente.telefono:
                cliente.telefono = form.telefono.data.strip()
        db.session.add(usuario)
        try:
            safe_commit()
            logger.info("Nuevo usuario cliente registrado: %s", correo)
            try:
                from services.notification_service import NotificationService
                NotificationService.notify_staff(
                    "sistema",
                    "Nuevo cliente registrado",
                    f"{form.nombre.data.strip()} creó una cuenta de cliente ({correo}).",
                    url_for("clientes.listar"),
                )
            except Exception as ne:
                logger.warning("No se pudo notificar registro de cliente: %s", ne)
            login_user(usuario)
            if request.is_json:
                return jsonify({"success": True, "message": "Registro exitoso."})
            flash("¡Bienvenido/a a SIAM! Tu cuenta fue creada.", "success")
            return redirect(url_for("portal.index"))
        except Exception:
            db.session.rollback()
            logger.exception("Error registrando usuario %s", correo)
            mensaje = "No se pudo completar el registro. Intenta nuevamente."
            if request.is_json:
                return json_error(mensaje)
            flash(mensaje, "danger")
            return render_template("auth/register.html", form=form)
    return render_template("auth/register.html", form=form)


@auth_bp.route("/registrar-admin", methods=["GET", "POST"])
def registrar_admin() -> Any:
    """Registro de cuenta administrativa del taller."""
    if current_user.is_authenticated:
        if current_user.es_cliente:
            return redirect(url_for("portal.index"))
        return redirect(url_for("dashboard.index"))
    form = AdminRegisterForm()
    if form.validate_on_submit():
        correo = form.correo.data.strip().lower()
        if Usuario.query.filter_by(correo=correo).first():
            flash("El correo ya está registrado", "danger")
            return render_template("auth/registrar_admin.html", form=form)
        usuario = Usuario(
            nombre=form.nombre.data.strip(),
            correo=correo,
            rol="admin",
        )
        usuario.set_password(form.password.data)
        db.session.add(usuario)
        try:
            safe_commit()
            logger.info("Nueva cuenta administrativa registrada: %s", correo)
            try:
                from services.notification_service import NotificationService
                NotificationService.notify_staff(
                    "sistema",
                    "Nueva cuenta administrativa",
                    f"Se creó la cuenta administrativa para {correo}.",
                    url_for("configuracion.index"),
                )
            except Exception as ne:
                logger.warning("No se pudo notificar nueva cuenta admin: %s", ne)
            flash("Cuenta administrativa creada. Inicia sesión.", "success")
            return redirect(url_for("auth.login"))
        except Exception:
            db.session.rollback()
            logger.exception("Error registrando administrador %s", correo)
            flash("No se pudo completar el registro. Intenta nuevamente.", "danger")
    return render_template("auth/registrar_admin.html", form=form)
