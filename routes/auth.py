import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError

from models import Usuario, Cliente
from database.db import db
from forms import LoginForm, RegisterForm, AdminRegisterForm
from database.commit import safe_commit, json_success, json_error

logger = logging.getLogger("siam.routes.auth")
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


class RegistroError(Exception):
    """Error de dominio del registro con mensaje seguro para el usuario."""

    def __init__(self, mensaje: str):
        self.mensaje = mensaje
        super().__init__(mensaje)


def _existe_admin() -> bool:
    """¿Existe al menos una cuenta de administrador?

    Patrón de degradación igual al resto de la app (landing, /health y
    context processors): si la BD está caída o aún sin migrar, se devuelve
    True (fail-closed: jamás se habilita el bootstrap administrativo con una
    BD incierta) y la excepción real queda completa y visible en el log.
    """
    try:
        return Usuario.query.filter_by(rol="admin").count() > 0
    except Exception:
        db.session.rollback()
        logger.exception("No se pudo consultar si existe un administrador")
        return True


def _mensaje_duplicado(correo: str, documento: str) -> str:
    """Mensaje amigable tras una violación de unicidad (POST-rollback).

    Nunca lanza: si la re-consulta falla, devuelve el mensaje genérico.
    """
    try:
        if Usuario.query.filter_by(correo=correo).first():
            return "El correo ya está registrado"
        if documento and Cliente.query.filter(Cliente.cedula == documento).first():
            return "Ese documento ya está registrado"
    except Exception:
        db.session.rollback()
    return "No se pudo completar el registro. Intenta nuevamente."


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
    permite_registrar_admin = not _existe_admin()
    if form.validate_on_submit():
        correo = form.correo.data.strip().lower()
        password = form.password.data
        usuario: Usuario | None = Usuario.query.filter_by(correo=correo).first()
        if usuario and usuario.check_password(password):
            if not usuario.activo:
                flash("Tu cuenta está desactivada. Contacta al administrador.", "danger")
                return render_template("auth/login.html", form=form, area=area, permite_registrar_admin=permite_registrar_admin)
            login_user(usuario, remember=request.form.get("remember") == "on")
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
    return render_template("auth/login.html", form=form, area=area, permite_registrar_admin=permite_registrar_admin)


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
        try:
            if Usuario.query.filter_by(correo=correo).first():
                raise RegistroError("El correo ya está registrado")
            cliente = Cliente.query.filter(db.func.lower(Cliente.correo) == correo).first()
            por_documento = Cliente.query.filter(Cliente.cedula == documento).first() if documento else None
            # Un documento ya usado solo es válido si pertenece al mismo cliente
            # (vinculación por correo); nunca permite tomar registros ajenos.
            if por_documento and (not cliente or por_documento.id != cliente.id):
                if not cliente and por_documento and not por_documento.correo:
                    cliente = por_documento
                elif por_documento:
                    raise RegistroError("Ese documento ya está registrado")
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
            safe_commit()
        except RegistroError as e:
            db.session.rollback()
            logger.warning("Registro rechazado (%s): %s", e.mensaje, correo)
            if request.is_json:
                return json_error(e.mensaje, status=400)
            flash(e.mensaje, "danger")
            return render_template("auth/register.html", form=form)
        except IntegrityError:
            db.session.rollback()
            # Excepción real y visible en el log del servidor (nunca al cliente).
            logger.exception("Registro con conflicto de unicidad: %s", correo)
            if request.is_json:
                return json_error(_mensaje_duplicado(correo, documento), status=400)
            flash(_mensaje_duplicado(correo, documento), "danger")
            return render_template("auth/register.html", form=form)
        except Exception:
            db.session.rollback()
            logger.exception("Error registrando usuario %s", correo)
            mensaje = "No se pudo completar el registro. Intenta nuevamente."
            if request.is_json:
                return json_error(mensaje)
            flash(mensaje, "danger")
            return render_template("auth/register.html", form=form)
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
    return render_template("auth/register.html", form=form)


@auth_bp.route("/registrar-admin", methods=["GET", "POST"])
def registrar_admin() -> Any:
    """Registro de cuenta administrativa del taller.

    Sólo es el bootstrap de la primera instalación: si ya existe una cuenta
    con rol admin, la ruta redirige al login (evita que cualquier visitante
    anónimo cree cuentas de administrador en producción).
    """
    if current_user.is_authenticated:
        if current_user.es_cliente:
            return redirect(url_for("portal.index"))
        return redirect(url_for("dashboard.index"))
    if _existe_admin():
        flash("Ya existe una cuenta de administrador. Inicia sesión para gestionar SIAM.", "warning")
        return redirect(url_for("auth.login"))
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
